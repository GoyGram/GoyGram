// CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList};
use pyo3::exceptions::PyRuntimeError;
use pyo3::exceptions::PyValueError;
use pyo3::ToPyObject;
use aes_gcm::{Aes256Gcm, KeyInit, aead::{Aead, Payload}, Nonce};
use serde::{Deserialize, Serialize};
use serde_json;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

struct Schema {
    methods: HashMap<String, Arc<TlMethod>>,
    ctors: HashMap<String, Arc<TlConstructor>>,
    by_cid: HashMap<u32, (Arc<str>, Arc<TlConstructor>)>,
    layer: u32,
}

static SCHEMA: RwLock<Option<Arc<Schema>>> = RwLock::new(None);

fn read_guard<T>(lock: &RwLock<T>) -> std::sync::RwLockReadGuard<'_, T> {
    lock.read().unwrap_or_else(|e| e.into_inner())
}

fn write_guard<T>(lock: &RwLock<T>) -> std::sync::RwLockWriteGuard<'_, T> {
    lock.write().unwrap_or_else(|e| e.into_inner())
}

fn schema_arc() -> Option<Arc<Schema>> {
    read_guard(&SCHEMA).clone()
}

fn install_schema(layer: u32, methods: HashMap<String, TlMethod>, ctors: HashMap<String, TlConstructor>) {
    let methods: HashMap<String, Arc<TlMethod>> = methods.into_iter().map(|(k, v)| (k, Arc::new(v))).collect();
    let mut by_cid = HashMap::with_capacity(ctors.len());
    let ctors: HashMap<String, Arc<TlConstructor>> = ctors.into_iter().map(|(k, v)| {
        let a = Arc::new(v);
        by_cid.insert(a.cid, (Arc::<str>::from(k.as_str()), a.clone()));
        (k, a)
    }).collect();
    *write_guard(&SCHEMA) = Some(Arc::new(Schema { methods, ctors, by_cid, layer }));
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TlFieldDef {
    name: String,
    #[serde(rename = "type")]
    ftype: String,
    #[serde(default)]
    flag_bit: Option<u32>,
    #[serde(default)]
    flags_group: Option<String>,
    #[serde(default)]
    is_bare: bool,
    #[serde(default)]
    is_vector: bool,
    #[serde(default)]
    vector_inner: Option<String>,
    #[serde(default)]
    vector_inner_is_vector: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TlMethod {
    cid: u32,
    fields: Vec<TlFieldDef>,
    #[serde(default)]
    has_flags: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TlConstructor {
    cid: u32,
    fields: Vec<TlFieldDef>,
    #[serde(default)]
    has_flags: bool,
}

#[derive(Debug, Deserialize)]
struct SchemaInput {
    #[serde(default)]
    layer: u32,
    methods: HashMap<String, TlMethod>,
    #[serde(default)]
    constructors: HashMap<String, TlConstructor>,
}

static BOOTSTRAP_SCHEMA_JSON: &str = include_str!("bootstrap.json");

fn apply_bootstrap() {
    if schema_arc().is_some() {
        return;
    }
    if let Ok(raw) = serde_json::from_str::<SchemaInput>(BOOTSTRAP_SCHEMA_JSON) {
        install_schema(raw.layer, raw.methods, raw.constructors);
    }
}

fn info_dict(py: Python<'_>, layer: u32, methods: usize, constructors: usize) -> PyResult<PyObject> {
    let d = PyDict::new_bound(py);
    d.set_item("layer", layer)?;
    d.set_item("methods", methods as u32)?;
    d.set_item("constructors", constructors as u32)?;
    Ok(d.into_any().unbind())
}

#[pyfunction]
fn load_schema(py: Python<'_>, schema_json: &str) -> PyResult<PyObject> {
    let raw: SchemaInput = match serde_json::from_str::<SchemaInput>(schema_json) {
        Ok(s) => s,
        Err(_) => {
            let methods_map: HashMap<String, TlMethod> = serde_json::from_str(schema_json)
                .map_err(|e| PyValueError::new_err(format!("schema parsing failed: {}", e)))?;
            SchemaInput {
                layer: 0,
                methods: methods_map,
                constructors: HashMap::new(),
            }
        }
    };
    let methods_n = raw.methods.len();
    let ctors_n = raw.constructors.len();
    let layer = raw.layer;
    install_schema(layer, raw.methods, raw.constructors);
    info_dict(py, layer, methods_n, ctors_n)
}

#[pyfunction]
fn schema_info(py: Python<'_>) -> PyResult<PyObject> {
    match schema_arc() {
        Some(s) => info_dict(py, s.layer, s.methods.len(), s.ctors.len()),
        None => info_dict(py, 0, 0, 0),
    }
}

fn get_ctor_by_cid(cid: u32) -> Option<(Arc<str>, Arc<TlConstructor>)> {
    schema_arc()?.by_cid.get(&cid).cloned()
}

fn read_u32(data: &[u8], pos: &mut usize) -> Result<u32, String> {
    let end = match pos.checked_add(4) {
        Some(e) => e,
        None => return Err("unexpected eof".to_string()),
    };
    if end > data.len() {
        return Err("unexpected eof".to_string());
    }
    let mut buf = [0u8; 4];
    buf.copy_from_slice(&data[*pos..end]);
    *pos = end;
    Ok(u32::from_le_bytes(buf))
}

fn read_i32(data: &[u8], pos: &mut usize) -> Result<i32, String> {
    Ok(read_u32(data, pos)? as i32)
}

fn read_i64(data: &[u8], pos: &mut usize) -> Result<i64, String> {
    let end = match pos.checked_add(8) {
        Some(e) => e,
        None => return Err("unexpected eof".to_string()),
    };
    if end > data.len() {
        return Err("unexpected eof".to_string());
    }
    let mut buf = [0u8; 8];
    buf.copy_from_slice(&data[*pos..end]);
    *pos = end;
    Ok(i64::from_le_bytes(buf))
}

fn read_f64(data: &[u8], pos: &mut usize) -> Result<f64, String> {
    let end = match pos.checked_add(8) {
        Some(e) => e,
        None => return Err("unexpected eof".to_string()),
    };
    if end > data.len() {
        return Err("unexpected eof".to_string());
    }
    let mut buf = [0u8; 8];
    buf.copy_from_slice(&data[*pos..end]);
    *pos = end;
    Ok(f64::from_le_bytes(buf))
}

fn read_bytes(data: &[u8], pos: &mut usize, len: usize) -> Result<Vec<u8>, String> {
    let end = match pos.checked_add(len) {
        Some(e) => e,
        None => return Err("unexpected eof".to_string()),
    };
    if end > data.len() {
        return Err("unexpected eof".to_string());
    }
    let v = data[*pos..end].to_vec();
    *pos = end;
    Ok(v)
}

fn skip_padding(data: &[u8], pos: &mut usize, padding: usize) -> Result<(), String> {
    if padding == 0 {
        return Ok(());
    }
    let end = match pos.checked_add(padding) {
        Some(e) => e,
        None => return Err("unexpected eof".to_string()),
    };
    if end > data.len() {
        return Err("unexpected eof".to_string());
    }
    *pos = end;
    Ok(())
}

fn read_tl_string(data: &[u8], pos: &mut usize) -> Result<String, String> {
    if *pos >= data.len() {
        return Err("unexpected eof".to_string());
    }
    let len = data[*pos] as usize;
    *pos += 1;
    let str_len = if len <= 253 {
        len
    } else if len == 254 {
        if *pos + 3 > data.len() {
            return Err("unexpected eof".to_string());
        }
        let l = u32::from_le_bytes([data[*pos], data[*pos + 1], data[*pos + 2], 0]) as usize;
        *pos += 3;
        l
    } else {
        return Err("bad string len".to_string());
    };
    let raw = read_bytes(data, pos, str_len)?;
    let header = 1 + if len <= 253 { 0 } else { 3 };
    let padding = (4 - ((header + str_len) % 4)) % 4;
    skip_padding(data, pos, padding)?;
    String::from_utf8(raw).map_err(|e| format!("utf8: {}", e))
}

fn read_tl_bytes_raw(data: &[u8], pos: &mut usize) -> Result<Vec<u8>, String> {
    if *pos >= data.len() {
        return Err("unexpected eof".to_string());
    }
    let len = data[*pos] as usize;
    *pos += 1;
    let byte_len = if len <= 253 {
        len
    } else if len == 254 {
        if *pos + 3 > data.len() {
            return Err("unexpected eof".to_string());
        }
        let l = u32::from_le_bytes([data[*pos], data[*pos + 1], data[*pos + 2], 0]) as usize;
        *pos += 3;
        l
    } else {
        return Err("bad bytes len".to_string());
    };
    let raw = read_bytes(data, pos, byte_len)?;
    let header = 1 + if len <= 253 { 0 } else { 3 };
    let padding = (4 - ((header + byte_len) % 4)) % 4;
    skip_padding(data, pos, padding)?;
    Ok(raw)
}

fn read_field_value(py: Python<'_>, data: &[u8], pos: &mut usize, f: &TlFieldDef) -> PyResult<PyObject> {
    match f.ftype.as_str() {
        "#" => Ok(read_u32(data, pos).map_err(PyValueError::new_err)?.to_object(py)),
        "int" | "Int" => Ok(read_i32(data, pos).map_err(PyValueError::new_err)?.to_object(py)),
        "long" | "Long" => Ok(read_i64(data, pos).map_err(PyValueError::new_err)?.to_object(py)),
        "int128" => {
            let b = read_bytes(data, pos, 16).map_err(PyValueError::new_err)?;
            Ok(hex::encode(b).to_object(py))
        }
        "int256" => {
            let b = read_bytes(data, pos, 32).map_err(PyValueError::new_err)?;
            Ok(hex::encode(b).to_object(py))
        }
        "string" | "String" => {
            let s = read_tl_string(data, pos).map_err(PyValueError::new_err)?;
            Ok(s.to_object(py))
        }
        "bytes" | "Bytes" => {
            let b = read_tl_bytes_raw(data, pos).map_err(PyValueError::new_err)?;
            Ok(hex::encode(b).to_object(py))
        }
        "double" | "Double" => Ok(read_f64(data, pos).map_err(PyValueError::new_err)?.to_object(py)),
        "Bool" | "boolTrue" | "boolFalse" => {
            let cid = read_u32(data, pos).map_err(PyValueError::new_err)?;
            Ok((cid == 0x997275b5).to_object(py))
        }
        "true" | "True" => Ok(true.to_object(py)),
        _ => {
            if f.is_vector {
                read_tl_vector(py, data, pos, f)
            } else {
                deserialize_tl(py, data, pos)
            }
        }
    }
}

fn read_tl_vector(py: Python<'_>, data: &[u8], pos: &mut usize, f: &TlFieldDef) -> PyResult<PyObject> {
    let vec_cid = read_u32(data, pos).map_err(PyValueError::new_err)?;
    if vec_cid != 0x1cb5c415 {
        return Err(PyValueError::new_err(format!("not a vector: {:08x}", vec_cid)));
    }
    let count = read_i32(data, pos).map_err(PyValueError::new_err)?;
    if count < 0 || count > 1_000_000 {
        return Err(PyValueError::new_err("invalid vector count"));
    }
    let count = count as usize;
    let inner_type = f.vector_inner.as_deref().unwrap_or("int");
    let inner_field = TlFieldDef {
        name: "item".to_string(),
        ftype: inner_type.to_string(),
        flag_bit: None,
        flags_group: None,
        is_bare: false,
        is_vector: f.vector_inner_is_vector,
        vector_inner: if f.vector_inner_is_vector { Some("int".to_string()) } else { None },
        vector_inner_is_vector: false,
    };
    let arr = PyList::empty_bound(py);
    for _ in 0..count {
        arr.append(read_field_value(py, data, pos, &inner_field)?)?;
    }
    Ok(arr.into_any().unbind())
}

fn deserialize_fields<'py>(
    py: Python<'py>,
    data: &[u8],
    pos: &mut usize,
    fields: &[TlFieldDef],
    has_flags: bool,
    name: &str,
) -> PyResult<Bound<'py, PyDict>> {
    let obj = PyDict::new_bound(py);
    obj.set_item("_", name)?;
    let mut flags = 0u32;
    let mut flags2 = 0u32;

    for f in fields {
        if f.ftype == "#" {
            let val = read_u32(data, pos).map_err(PyValueError::new_err)?;
            if f.name == "flags2" {
                flags2 = val;
            } else {
                flags = val;
            }
            obj.set_item(&f.name, val)?;
            continue;
        }

        if has_flags {
            if let Some(bit) = f.flag_bit {
                let group = f.flags_group.as_deref().unwrap_or("flags");
                let flags_val = if group == "flags2" { flags2 } else { flags };
                if flags_val & (1 << bit) == 0 {
                    if f.is_bare {
                        obj.set_item(&f.name, false)?;
                    }
                    continue;
                }
                if f.is_bare {
                    obj.set_item(&f.name, true)?;
                    continue;
                }
            }
        }

        let val = read_field_value(py, data, pos, f)?;
        obj.set_item(&f.name, val)?;
    }

    Ok(obj)
}

fn deserialize_tl(py: Python<'_>, data: &[u8], pos: &mut usize) -> PyResult<PyObject> {
    let cid = read_u32(data, pos).map_err(PyValueError::new_err)?;
    if cid == 0x1cb5c415 {
        let count = read_i32(data, pos).map_err(PyValueError::new_err)?;
        if count < 0 || count > 1_000_000 {
            return Err(PyValueError::new_err("invalid vector count"));
        }
        let count = count as usize;
        let arr = PyList::empty_bound(py);
        for _ in 0..count {
            arr.append(deserialize_tl(py, data, pos)?)?;
        }
        return Ok(arr.into_any().unbind());
    }
    if let Some((name, ctor)) = get_ctor_by_cid(cid) {
        let result = deserialize_fields(py, data, pos, &ctor.fields, ctor.has_flags, name.as_ref())?;
        Ok(result.into_any().unbind())
    } else {
        let start = *pos - 4;
        let remaining = &data[start..];
        *pos = data.len();
        let d = PyDict::new_bound(py);
        d.set_item("_", "unknownConstructor")?;
        d.set_item("cid", cid)?;
        d.set_item("raw", hex::encode(remaining))?;
        Ok(d.into_any().unbind())
    }
}

#[pyfunction]
fn deserialize_constructor(py: Python<'_>, data: &[u8]) -> PyResult<PyObject> {
    let mut pos = 0;
    deserialize_tl(py, data, &mut pos)
}

fn py_to_value(obj: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if obj.is_none() {
        return Ok(serde_json::Value::Null);
    }
    if let Ok(b) = obj.extract::<bool>() {
        return Ok(serde_json::Value::Bool(b));
    }
    if let Ok(i) = obj.extract::<i64>() {
        return Ok(serde_json::json!(i));
    }
    if let Ok(u) = obj.extract::<u64>() {
        return Ok(serde_json::json!(u));
    }
    if let Ok(f) = obj.extract::<f64>() {
        return Ok(serde_json::json!(f));
    }
    if let Ok(s) = obj.extract::<String>() {
        return Ok(serde_json::Value::String(s));
    }
    if let Ok(b) = obj.downcast::<PyBytes>() {
        return Ok(serde_json::Value::String(hex::encode(b.as_bytes())));
    }
    if let Ok(d) = obj.downcast::<PyDict>() {
        let mut map = serde_json::Map::new();
        for (k, v) in d.iter() {
            let key: String = k.extract()?;
            map.insert(key, py_to_value(&v)?);
        }
        return Ok(serde_json::Value::Object(map));
    }
    if let Ok(l) = obj.downcast::<PyList>() {
        let mut arr = Vec::with_capacity(l.len());
        for item in l.iter() {
            arr.push(py_to_value(&item)?);
        }
        return Ok(serde_json::Value::Array(arr));
    }
    if let Ok(t) = obj.downcast::<pyo3::types::PyTuple>() {
        let mut arr = Vec::with_capacity(t.len());
        for item in t.iter() {
            arr.push(py_to_value(&item)?);
        }
        return Ok(serde_json::Value::Array(arr));
    }
    Err(PyValueError::new_err(format!(
        "cannot convert {} to TL args",
        obj.get_type().name()?
    )))
}

fn args_to_value(args: &Bound<'_, PyAny>) -> PyResult<serde_json::Value> {
    if let Ok(s) = args.extract::<&str>() {
        return serde_json::from_str(s)
            .map_err(|e| PyValueError::new_err(format!("args parsing failed: {}", e)));
    }
    py_to_value(args)
}

fn serialize_tl(name: &str, args: &serde_json::Value, cid: u32, fields: &[TlFieldDef], has_flags: bool) -> PyResult<Vec<u8>> {
    let mut buf: Vec<u8> = Vec::new();
    buf.extend_from_slice(&cid.to_le_bytes());

    if has_flags {
        let mut flags = 0u32;
        let mut flags2 = 0u32;

        for f in fields {
            if let Some(bit) = f.flag_bit {
                let group = f.flags_group.as_deref().unwrap_or("flags");
                let val = args.get(&f.name);
                let has_val = match val {
                    Some(serde_json::Value::Null) | None => false,
                    Some(serde_json::Value::Bool(true)) if f.is_bare => true,
                    Some(serde_json::Value::Bool(false)) if f.is_bare => false,
                    _ => val.is_some(),
                };
                if has_val {
                    if group == "flags2" {
                        flags2 |= 1 << bit;
                    } else {
                        flags |= 1 << bit;
                    }
                }
            }
        }

        for f in fields {
            if f.ftype == "#" {
                let fv = if f.name == "flags2" { flags2 } else { flags };
                buf.extend_from_slice(&fv.to_le_bytes());
                continue;
            }

            if f.flag_bit.is_some() {
                let val = args.get(&f.name);
                let has_val = match val {
                    Some(serde_json::Value::Null) | None => false,
                    Some(serde_json::Value::Bool(true)) if f.is_bare => true,
                    Some(serde_json::Value::Bool(false)) if f.is_bare => false,
                    _ => val.is_some(),
                };

                if !has_val {
                    continue;
                }

                if f.is_bare {
                    continue;
                }

                let fb = encode_field_value(f, val.unwrap_or(&serde_json::Value::Null))
                    .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
                buf.extend_from_slice(&fb);
            } else {
                let val = args.get(&f.name).ok_or_else(|| PyValueError::new_err(format!("{}: missing required field {}", name, f.name)))?;
                let fb = encode_field_value(f, val)
                    .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
                buf.extend_from_slice(&fb);
            }
        }
    } else {
        for f in fields {
            let val = args.get(&f.name).ok_or_else(|| PyValueError::new_err(format!("{}: missing required field {}", name, f.name)))?;
            let fb = encode_field_value(f, val)
                .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
            buf.extend_from_slice(&fb);
        }
    }

    Ok(buf)
}

fn encode_field_value(f: &TlFieldDef, val: &serde_json::Value) -> Result<Vec<u8>, String> {
    match f.ftype.as_str() {
        "#" => {
            let n = val.as_i64().ok_or("flags not int")? as u32;
            Ok(n.to_le_bytes().to_vec())
        }
        "int" | "Int" => {
            let n = val.as_i64().ok_or("int expected")? as i32;
            Ok(n.to_le_bytes().to_vec())
        }
        "long" | "Long" => {
            if let Some(s) = val.as_str() {
                let bytes = hex::decode(s).map_err(|e| format!("hex: {}", e))?;
                Ok(bytes)
            } else if val.is_number() {
                let n = val.as_i64().ok_or("long expected")?;
                Ok(n.to_le_bytes().to_vec())
            } else {
                Err(format!("cannot encode field {} as long", f.name))
            }
        }
        "int128" => {
            if let Some(n) = val.as_i64() {
                let mut out = vec![0u8; 16];
                out[..8].copy_from_slice(&n.to_le_bytes());
                Ok(out)
            } else if let Some(s) = val.as_str() {
                let bytes = hex::decode(s).map_err(|e| format!("hex: {}", e))?;
                if bytes.len() != 16 { return Err("int128 must be 16 bytes".to_string()); }
                Ok(bytes)
            } else { Err(format!("cannot encode field {} as int128", f.name)) }
        }
        "int256" => {
            if let Some(n) = val.as_i64() {
                let mut out = vec![0u8; 32];
                out[..8].copy_from_slice(&n.to_le_bytes());
                Ok(out)
            } else if let Some(s) = val.as_str() {
                let bytes = hex::decode(s).map_err(|e| format!("hex: {}", e))?;
                if bytes.len() != 32 { return Err("int256 must be 32 bytes".to_string()); }
                Ok(bytes)
            } else { Err(format!("cannot encode field {} as int256", f.name)) }
        }
        "string" | "String" => {
            let s = val.as_str().unwrap_or("");
            encode_tl_string(s)
        }
        "bytes" | "Bytes" => {
            if let Some(s) = val.as_str() {
                let b = hex::decode(s).map_err(|e| format!("hex: {}", e))?;
                encode_tl_bytes(&b)
            } else if let Some(arr) = val.as_array() {
                let mut b = Vec::new();
                for v in arr {
                    let n = v.as_u64().ok_or("byte expected")? as u8;
                    b.push(n);
                }
                encode_tl_bytes(&b)
            } else {
                Err(format!("cannot encode field {} as bytes", f.name))
            }
        }
        "double" | "Double" => {
            let n = val.as_f64().ok_or("double expected")?;
            Ok(n.to_le_bytes().to_vec())
        }
        "Bool" | "boolTrue" | "boolFalse" => {
            let b = val.as_bool().unwrap_or(false);
            if b {
                Ok(0x997275b5u32.to_le_bytes().to_vec())
            } else {
                Ok(0xbc799737u32.to_le_bytes().to_vec())
            }
        }
        "true" | "True" => {
            Ok(vec![])
        }
        _ => {
            if f.is_vector {
                encode_tl_vector(f, val)
            } else if f.ftype.starts_with('!') {
                if let Some(s) = val.as_str() {
                    if s.is_empty() {
                        return Ok(vec![]);
                    }
                    hex::decode(s).map_err(|e| format!("hex: {}", e))
                } else {
                    Ok(vec![])
                }
            } else if let Some(s) = val.as_str() {
                if s.is_empty() {
                    return Ok(vec![]);
                }
                hex::decode(s).map_err(|e| format!("hex: {}", e))
            } else if val.is_number() {
                let n = val.as_i64().unwrap_or(0);
                Ok(n.to_le_bytes().to_vec())
            } else if val.is_object() {
                let ctor_name = val.get("_").and_then(|x| x.as_str()).unwrap_or(f.ftype.as_str());
                let def = schema_arc().and_then(|s| s.ctors.get(ctor_name).cloned());
                if let Some(def) = def {
                    serialize_tl(ctor_name, val, def.cid, &def.fields, def.has_flags)
                        .map_err(|e| e.to_string())
                } else {
                    let keys: Vec<&str> = val.as_object().map(|m| m.keys().map(|k| k.as_str()).collect()).unwrap_or_default();
                    Err(format!("unknown constructor type {} (keys {:?})", ctor_name, keys))
                }
            } else {
                Err(format!("unknown TL field type {}", f.ftype))
            }
        }
    }
}

fn encode_tl_string(s: &str) -> Result<Vec<u8>, String> {
    let b = s.as_bytes();
    let mut buf = Vec::new();
    if b.len() <= 253 {
        buf.push(b.len() as u8);
    } else {
        buf.push(254);
        buf.extend_from_slice(&(b.len() as u32).to_le_bytes()[..3]);
    }
    buf.extend_from_slice(b);
    while buf.len() % 4 != 0 {
        buf.push(0);
    }
    Ok(buf)
}

fn encode_tl_bytes(b: &[u8]) -> Result<Vec<u8>, String> {
    let mut buf = Vec::new();
    if b.len() <= 253 {
        buf.push(b.len() as u8);
    } else {
        buf.push(254);
        buf.extend_from_slice(&(b.len() as u32).to_le_bytes()[..3]);
    }
    buf.extend_from_slice(b);
    while buf.len() % 4 != 0 {
        buf.push(0);
    }
    Ok(buf)
}

fn encode_tl_vector(f: &TlFieldDef, val: &serde_json::Value) -> Result<Vec<u8>, String> {
    let arr = val.as_array().ok_or("vector expected array")?;
    let inner_type = f.vector_inner.as_deref().unwrap_or("int");

    let mut buf: Vec<u8> = Vec::new();
    buf.extend_from_slice(&0x1cb5c415u32.to_le_bytes());
    buf.extend_from_slice(&(arr.len() as u32).to_le_bytes());

    for item in arr {
        let inner_field = TlFieldDef {
            name: "item".to_string(),
            ftype: inner_type.to_string(),
            flag_bit: None,
            flags_group: None,
            is_bare: false,
            is_vector: f.vector_inner_is_vector,
            vector_inner: if f.vector_inner_is_vector { Some("int".to_string()) } else { None },
            vector_inner_is_vector: false,
        };
        let eb = encode_field_value(&inner_field, item)?;
        buf.extend_from_slice(&eb);
    }

    Ok(buf)
}

#[pyfunction]
fn serialize_method(py: Python<'_>, method: &str, args: Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
    let schema = schema_arc().ok_or_else(|| PyRuntimeError::new_err("schema not loaded"))?;
    let tl = schema.methods.get(method)
        .ok_or_else(|| PyValueError::new_err(format!("unknown method: {}", method)))?;
    let value = args_to_value(&args)?;
    let data = serialize_tl(method, &value, tl.cid, &tl.fields, tl.has_flags)?;
    Ok(PyBytes::new_bound(py, &data).unbind())
}

#[pyfunction]
fn serialize_constructor(py: Python<'_>, name: &str, args: Bound<'_, PyAny>) -> PyResult<Py<PyBytes>> {
    let schema = schema_arc().ok_or_else(|| PyRuntimeError::new_err("schema not loaded"))?;
    let tl = schema.ctors.get(name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown constructor: {}", name)))?;
    let value = args_to_value(&args)?;
    let data = serialize_tl(name, &value, tl.cid, &tl.fields, tl.has_flags)?;
    Ok(PyBytes::new_bound(py, &data).unbind())
}

#[cfg(target_arch = "x86_64")]
unsafe fn ige_expand_keys(key: &[u8; 32]) -> [std::arch::x86_64::__m128i; 15] {
    use std::arch::x86_64::*;
    let mut keys: [__m128i; 15] = std::mem::zeroed();
    let kp = key.as_ptr() as *const __m128i;
    keys[0] = _mm_loadu_si128(kp);
    keys[1] = _mm_loadu_si128(kp.add(1));

    macro_rules! expand_round {
        ($pos:expr, $round:expr) => {
            let mut t1 = keys[$pos - 2];
            let mut t4;
            let mut t3 = keys[$pos - 1];
            let mut t2 = _mm_aeskeygenassist_si128(t3, $round);
            t2 = _mm_shuffle_epi32(t2, 0xff);
            t4 = _mm_slli_si128(t1, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t4 = _mm_slli_si128(t4, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t4 = _mm_slli_si128(t4, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t1 = _mm_xor_si128(t1, t2);
            keys[$pos] = t1;

            let mut t4b = _mm_aeskeygenassist_si128(t1, 0x00);
            t4b = _mm_shuffle_epi32(t4b, 0xaa);
            let mut t5 = _mm_slli_si128(t3, 0x4);
            t3 = _mm_xor_si128(t3, t5);
            t5 = _mm_slli_si128(t5, 0x4);
            t3 = _mm_xor_si128(t3, t5);
            t5 = _mm_slli_si128(t5, 0x4);
            t3 = _mm_xor_si128(t3, t5);
            t3 = _mm_xor_si128(t3, t4b);
            keys[$pos + 1] = t3;
        };
    }
    macro_rules! expand_round_last {
        ($pos:expr, $round:expr) => {
            let mut t1 = keys[$pos - 2];
            let t3 = keys[$pos - 1];
            let mut t2 = _mm_aeskeygenassist_si128(t3, $round);
            t2 = _mm_shuffle_epi32(t2, 0xff);
            let mut t4 = _mm_slli_si128(t1, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t4 = _mm_slli_si128(t4, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t4 = _mm_slli_si128(t4, 0x4);
            t1 = _mm_xor_si128(t1, t4);
            t1 = _mm_xor_si128(t1, t2);
            keys[$pos] = t1;
        };
    }

    expand_round!(2, 0x01);
    expand_round!(4, 0x02);
    expand_round!(6, 0x04);
    expand_round!(8, 0x08);
    expand_round!(10, 0x10);
    expand_round!(12, 0x20);
    expand_round_last!(14, 0x40);
    keys
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "aes")]
unsafe fn ige_inv_keys(keys: &[std::arch::x86_64::__m128i; 15]) -> [std::arch::x86_64::__m128i; 15] {
    use std::arch::x86_64::*;
    [
        keys[0],
        _mm_aesimc_si128(keys[1]),
        _mm_aesimc_si128(keys[2]),
        _mm_aesimc_si128(keys[3]),
        _mm_aesimc_si128(keys[4]),
        _mm_aesimc_si128(keys[5]),
        _mm_aesimc_si128(keys[6]),
        _mm_aesimc_si128(keys[7]),
        _mm_aesimc_si128(keys[8]),
        _mm_aesimc_si128(keys[9]),
        _mm_aesimc_si128(keys[10]),
        _mm_aesimc_si128(keys[11]),
        _mm_aesimc_si128(keys[12]),
        _mm_aesimc_si128(keys[13]),
        keys[14],
    ]
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "aes")]
unsafe fn aes_ige_x86(data: &[u8], key: &[u8; 32], iv: &[u8; 32], direction: u8) -> Vec<u8> {
    use std::arch::x86_64::*;
    let mut result = vec![0u8; data.len()];
    let enc_keys = ige_expand_keys(key);
    let dec_keys = if direction == 0 { ige_inv_keys(&enc_keys) } else { enc_keys };
    let mut x = if direction == 0 { _mm_loadu_si128(unsafe { iv.as_ptr().add(16) } as *const __m128i) } else { _mm_loadu_si128(iv.as_ptr() as *const __m128i) };
    let mut y = if direction == 0 { _mm_loadu_si128(iv.as_ptr() as *const __m128i) } else { _mm_loadu_si128(unsafe { iv.as_ptr().add(16) } as *const __m128i) };
    let mut off = 0usize;
    if direction == 0 {
        while off < data.len() {
            let m = _mm_loadu_si128(data.as_ptr().add(off) as *const __m128i);
            let mut t = _mm_xor_si128(m, x);
            t = _mm_xor_si128(t, dec_keys[14]);
            t = _mm_aesdec_si128(t, dec_keys[13]);
            t = _mm_aesdec_si128(t, dec_keys[12]);
            t = _mm_aesdec_si128(t, dec_keys[11]);
            t = _mm_aesdec_si128(t, dec_keys[10]);
            t = _mm_aesdec_si128(t, dec_keys[9]);
            t = _mm_aesdec_si128(t, dec_keys[8]);
            t = _mm_aesdec_si128(t, dec_keys[7]);
            t = _mm_aesdec_si128(t, dec_keys[6]);
            t = _mm_aesdec_si128(t, dec_keys[5]);
            t = _mm_aesdec_si128(t, dec_keys[4]);
            t = _mm_aesdec_si128(t, dec_keys[3]);
            t = _mm_aesdec_si128(t, dec_keys[2]);
            t = _mm_aesdec_si128(t, dec_keys[1]);
            let out = _mm_xor_si128(_mm_aesdeclast_si128(t, dec_keys[0]), y);
            _mm_storeu_si128(result.as_mut_ptr().add(off) as *mut __m128i, out);
            x = out;
            y = m;
            off += 16;
        }
    } else {
        while off < data.len() {
            let m = _mm_loadu_si128(data.as_ptr().add(off) as *const __m128i);
            let mut t = _mm_xor_si128(m, x);
            t = _mm_xor_si128(t, enc_keys[0]);
            t = _mm_aesenc_si128(t, enc_keys[1]);
            t = _mm_aesenc_si128(t, enc_keys[2]);
            t = _mm_aesenc_si128(t, enc_keys[3]);
            t = _mm_aesenc_si128(t, enc_keys[4]);
            t = _mm_aesenc_si128(t, enc_keys[5]);
            t = _mm_aesenc_si128(t, enc_keys[6]);
            t = _mm_aesenc_si128(t, enc_keys[7]);
            t = _mm_aesenc_si128(t, enc_keys[8]);
            t = _mm_aesenc_si128(t, enc_keys[9]);
            t = _mm_aesenc_si128(t, enc_keys[10]);
            t = _mm_aesenc_si128(t, enc_keys[11]);
            t = _mm_aesenc_si128(t, enc_keys[12]);
            t = _mm_aesenc_si128(t, enc_keys[13]);
            let out = _mm_xor_si128(_mm_aesenclast_si128(t, enc_keys[14]), y);
            _mm_storeu_si128(result.as_mut_ptr().add(off) as *mut __m128i, out);
            x = out;
            y = m;
            off += 16;
        }
    }
    result
}

#[pyfunction]
fn aes_ige_fast_path() -> bool {
    #[cfg(target_arch = "x86_64")]
    {
        std::arch::is_x86_feature_detected!("aes") && std::arch::is_x86_feature_detected!("sse2")
    }
    #[cfg(not(target_arch = "x86_64"))]
    { false }
}

fn aes_ige_impl(data: &[u8], key: &[u8], iv: &[u8], direction: u8) -> Result<Vec<u8>, String> {
    if data.len() % 16 != 0 { return Err("AES-IGE data length must be a multiple of 16".to_string()); }
    if key.len() != 32 { return Err("AES-IGE key must be 32 bytes".to_string()); }
    if iv.len() != 32 { return Err("AES-IGE IV must be 32 bytes".to_string()); }
    #[cfg(target_arch = "x86_64")]
    {
        if std::arch::is_x86_feature_detected!("aes") && std::arch::is_x86_feature_detected!("sse2") {
            let mut key_arr = [0u8; 32];
            let mut iv_arr = [0u8; 32];
            key_arr.copy_from_slice(key);
            iv_arr.copy_from_slice(iv);
            return Ok(unsafe { aes_ige_x86(data, &key_arr, &iv_arr, direction) });
        }
    }
    use aes::cipher::{BlockDecrypt, BlockEncrypt, KeyInit};
    use aes::Aes256;

    let cipher = Aes256::new_from_slice(key).map_err(|_| "invalid key size".to_string())?;
    let mut x = [0u8; 16];
    let mut y = [0u8; 16];
    x.copy_from_slice(&iv[..16]);
    y.copy_from_slice(&iv[16..32]);
    let mut result = data.to_vec();
    let bs = 16;
    let nblk = result.len() / bs;

    for i in 0..nblk {
        let off = i * bs;
        if direction == 0 {
            for j in 0..bs { result[off + j] ^= y[j]; }
            cipher.decrypt_block((&mut result[off..off + bs]).into());
            for j in 0..bs { result[off + j] ^= x[j]; }
            x.copy_from_slice(&data[off..off + bs]);
            y.copy_from_slice(&result[off..off + bs]);
        } else {
            for j in 0..bs { result[off + j] ^= x[j]; }
            cipher.encrypt_block((&mut result[off..off + bs]).into());
            for j in 0..bs { result[off + j] ^= y[j]; }
            x.copy_from_slice(&result[off..off + bs]);
            y.copy_from_slice(&data[off..off + bs]);
        }
    }

    Ok(result)
}

#[pyfunction]
fn aes_ige_enc(py: Python<'_>, data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Py<PyBytes>> {
    let out = aes_ige_impl(data, key, iv, 1).map_err(PyValueError::new_err)?;
    Ok(PyBytes::new_bound(py, &out).unbind())
}

#[pyfunction]
fn aes_ige_dec(py: Python<'_>, data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Py<PyBytes>> {
    let out = aes_ige_impl(data, key, iv, 0).map_err(PyValueError::new_err)?;
    Ok(PyBytes::new_bound(py, &out).unbind())
}

#[pyfunction]
fn aes_ige_enc_raw(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    aes_ige_impl(data, key, iv, 1).map_err(PyValueError::new_err)
}

#[pyfunction]
fn aes_ige_dec_raw(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    aes_ige_impl(data, key, iv, 0).map_err(PyValueError::new_err)
}

#[pyfunction]
fn aes_gcm_encrypt(py: Python<'_>, key: &[u8], nonce: &[u8], plaintext: &[u8], aad: &[u8]) -> PyResult<Py<PyBytes>> {
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|e| PyRuntimeError::new_err(format!("AES-GCM key error: {}", e)))?;
    let n = Nonce::from_slice(nonce);
    let ct = cipher.encrypt(n, Payload { msg: plaintext, aad })
        .map_err(|e| PyRuntimeError::new_err(format!("AES-GCM encrypt error: {}", e)))?;
    Ok(PyBytes::new_bound(py, &ct).unbind())
}

#[pyfunction]
fn aes_gcm_decrypt(py: Python<'_>, key: &[u8], nonce: &[u8], ciphertext: &[u8], aad: &[u8]) -> PyResult<Py<PyBytes>> {
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|e| PyRuntimeError::new_err(format!("AES-GCM key error: {}", e)))?;
    let n = Nonce::from_slice(nonce);
    let pt = cipher.decrypt(n, Payload { msg: ciphertext, aad })
        .map_err(|e| PyRuntimeError::new_err(format!("AES-GCM decrypt error: {}", e)))?;
    Ok(PyBytes::new_bound(py, &pt).unbind())
}

#[pyfunction]
fn cut(py: Python<'_>, data: &[u8], offset: usize, length: usize) -> PyResult<Py<PyBytes>> {
    if offset > data.len() { return Err(PyValueError::new_err("offset out of range")); }
    let end = offset + length.min(data.len() - offset);
    Ok(PyBytes::new_bound(py, &data[offset..end]).unbind())
}

#[pyfunction]
fn pack(py: Python<'_>, parts: Vec<Vec<u8>>) -> PyResult<Py<PyBytes>> {
    let mut out = Vec::new();
    for p in parts {
        out.extend_from_slice(&p);
    }
    Ok(PyBytes::new_bound(py, &out).unbind())
}

#[pymodule]
fn ext(m: &Bound<'_, PyModule>) -> PyResult<()> {
    apply_bootstrap();
    m.add_function(wrap_pyfunction!(load_schema, m)?)?;
    m.add_function(wrap_pyfunction!(schema_info, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_method, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_constructor, m)?)?;
    m.add_function(wrap_pyfunction!(deserialize_constructor, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_enc, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_fast_path, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_enc_raw, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec_raw, m)?)?;
    m.add_function(wrap_pyfunction!(aes_gcm_encrypt, m)?)?;
    m.add_function(wrap_pyfunction!(aes_gcm_decrypt, m)?)?;
    m.add_function(wrap_pyfunction!(cut, m)?)?;
    m.add_function(wrap_pyfunction!(pack, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::aes_ige_impl;

    #[test]
    fn ige_roundtrip() {
        let key = [0u8; 32];
        let iv = [1u8; 32];
        let plain = [42u8; 64];
        let enc = aes_ige_impl(&plain, &key, &iv, 1).unwrap();
        let dec = aes_ige_impl(&enc, &key, &iv, 0).unwrap();
        assert_eq!(&dec, &plain);
    }
}
