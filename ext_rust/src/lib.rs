// Rust extension: dynamic TL serialization with hot-reload
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use pyo3::exceptions::PyRuntimeError;
use pyo3::exceptions::PyValueError;
use serde::{Deserialize, Serialize};
use serde_json;
use std::collections::HashMap;
use std::sync::RwLock;

static METHODS: RwLock<Option<HashMap<String, TlMethod>>> = RwLock::new(None);
static CTORS: RwLock<Option<HashMap<String, TlConstructor>>> = RwLock::new(None);

#[derive(Debug, Clone, Serialize, Deserialize)]
struct TlFieldDef {
    name: String,
    #[serde(rename = "type")]
    ftype: String,
    #[serde(default)]
    flag_bit: Option<u32>,
    #[serde(default)]
    is_bare: bool,
    #[serde(default)]
    is_vector: bool,
    #[serde(default)]
    vector_inner: Option<String>,
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
    methods: HashMap<String, TlMethod>,
    #[serde(default)]
    constructors: HashMap<String, TlConstructor>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct SchemaInfo {
    layer: u32,
    #[serde(default)]
    methods: u32,
    #[serde(default)]
    constructors: u32,
}

fn pack_schema(methods: &HashMap<String, TlMethod>, ctors: &HashMap<String, TlConstructor>) -> SchemaInfo {
    SchemaInfo {
        layer: 0,
        methods: methods.len() as u32,
        constructors: ctors.len() as u32,
    }
}

static BOOTSTRAP_SCHEMA_JSON: &str = include_str!("bootstrap.json");

fn apply_bootstrap() {
    let mut m = METHODS.write().unwrap();
    let mut c = CTORS.write().unwrap();
    if m.is_none() && c.is_none() {
        if let Ok(raw) = serde_json::from_str::<SchemaInput>(BOOTSTRAP_SCHEMA_JSON) {
            *m = Some(raw.methods);
            *c = Some(raw.constructors);
        }
    }
}

#[pyfunction]
fn load_schema(schema_json: &str) -> PyResult<String> {
    let raw: SchemaInput = match serde_json::from_str::<SchemaInput>(schema_json) {
        Ok(s) => s,
        Err(_) => {
            let methods_map: HashMap<String, TlMethod> = serde_json::from_str(schema_json)
                .map_err(|e| PyValueError::new_err(format!("schema parsing failed: {}", e)))?;
            SchemaInput {
                methods: methods_map,
                constructors: HashMap::new(),
            }
        }
    };

    let info = SchemaInfo {
        layer: 0,
        methods: raw.methods.len() as u32,
        constructors: raw.constructors.len() as u32,
    };

    {
        let mut m = METHODS.write().unwrap();
        let mut c = CTORS.write().unwrap();
        *m = Some(raw.methods);
        *c = Some(raw.constructors);
    }

    Ok(serde_json::to_string(&info).unwrap())
}

#[pyfunction]
fn schema_info() -> PyResult<String> {
    let m = METHODS.read().unwrap();
    let c = CTORS.read().unwrap();
    match (&*m, &*c) {
        (Some(methods), Some(ctors)) => {
            let info = pack_schema(methods, ctors);
            Ok(serde_json::to_string(&info).unwrap())
        }
        _ => Ok(r#"{"methods":0,"constructors":0}"#.to_string()),
    }
}

fn serialize_tl(name: &str, args_json: &str, cid: u32, fields: &[TlFieldDef], has_flags: bool) -> PyResult<Vec<u8>> {
    let args: serde_json::Value = serde_json::from_str(args_json)
        .map_err(|e| PyValueError::new_err(format!("args parsing failed: {}", e)))?;

    let mut buf: Vec<u8> = Vec::new();
    buf.extend_from_slice(&cid.to_le_bytes());

    if has_flags {
        let mut flags_val: u32 = 0;

        for f in fields {
            if let Some(bit) = f.flag_bit {
                let val = args.get(&f.name);
                let has_val = match val {
                    Some(serde_json::Value::Null) | None => false,
                    Some(serde_json::Value::Bool(true)) if f.is_bare => true,
                    Some(serde_json::Value::Bool(false)) if f.is_bare => false,
                    _ => val.is_some(),
                };
                if has_val {
                    flags_val |= 1 << bit;
                }
            }
        }

        for f in fields {
            if f.ftype == "#" {
                buf.extend_from_slice(&flags_val.to_le_bytes());
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

                let fb = encode_field_value(&f, val.unwrap_or(&serde_json::Value::Null))
                    .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
                buf.extend_from_slice(&fb);
            } else {
                if let Some(ref val) = args.get(&f.name) {
                    let fb = encode_field_value(&f, val)
                        .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
                    buf.extend_from_slice(&fb);
                }
            }
        }
    } else {
        for f in fields {
            if let Some(ref val) = args.get(&f.name) {
                let fb = encode_field_value(&f, val)
                    .map_err(|e| PyValueError::new_err(format!("{}:{}: {}", name, f.name, e)))?;
                buf.extend_from_slice(&fb);
            }
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
        "long" | "Long" | "int128" | "int256" => {
            if val.is_string() {
                let s = val.as_str().unwrap();
                let bytes = hex::decode(s)
                    .map_err(|e| format!("hex: {}", e))?;
                Ok(bytes)
            } else if val.is_number() {
                let n = val.as_i64().ok_or("long expected")?;
                Ok(n.to_le_bytes().to_vec())
            } else {
                Err(format!("cannot encode field {} as long", f.name))
            }
        }
        "string" | "String" => {
            let s = val.as_str().unwrap_or("");
            encode_tl_string(s)
        }
        "bytes" | "Bytes" => {
            if val.is_string() {
                let s = val.as_str().unwrap();
                let b = hex::decode(s).map_err(|e| format!("hex: {}", e))?;
                encode_tl_bytes(&b)
            } else if val.is_array() {
                let mut b = Vec::new();
                for v in val.as_array().unwrap() {
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
                if val.is_string() {
                    let s = val.as_str().unwrap();
                    if s.is_empty() {
                        return Ok(vec![]);
                    }
                    hex::decode(s).map_err(|e| format!("hex: {}", e))
                } else {
                    Ok(vec![])
                }
            } else if val.is_string() {
                let s = val.as_str().unwrap();
                if s.is_empty() {
                    return Ok(vec![]);
                }
                hex::decode(s).map_err(|e| format!("hex: {}", e))
            } else if val.is_number() {
                let n = val.as_i64().unwrap_or(0);
                Ok(n.to_le_bytes().to_vec())
            } else {
                Ok(vec![])
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
            is_bare: false,
            is_vector: false,
            vector_inner: None,
        };
        let eb = encode_field_value(&inner_field, item)?;
        buf.extend_from_slice(&eb);
    }

    Ok(buf)
}

#[pyfunction]
fn serialize_method(py: Python<'_>, method: &str, args_json: &str) -> PyResult<Py<PyBytes>> {
    let m = METHODS.read().unwrap();
    let methods = m.as_ref()
        .ok_or_else(|| PyRuntimeError::new_err("schema not loaded"))?;

    let tl = methods.get(method)
        .ok_or_else(|| PyValueError::new_err(format!("unknown method: {}", method)))?;

    let data = serialize_tl(method, args_json, tl.cid, &tl.fields, tl.has_flags)?;
    Ok(PyBytes::new(py, &data).into())
}

#[pyfunction]
fn serialize_constructor(py: Python<'_>, name: &str, args_json: &str) -> PyResult<Py<PyBytes>> {
    let c = CTORS.read().unwrap();
    let ctors = c.as_ref()
        .ok_or_else(|| PyRuntimeError::new_err("schema not loaded"))?;

    let tl = ctors.get(name)
        .ok_or_else(|| PyValueError::new_err(format!("unknown constructor: {}", name)))?;

    let data = serialize_tl(name, args_json, tl.cid, &tl.fields, tl.has_flags)?;
    Ok(PyBytes::new(py, &data).into())
}

fn aes_ige_impl(data: &[u8], key: &[u8], iv: &[u8], direction: u8) -> Vec<u8> {
    use aes::cipher::{BlockDecrypt, BlockEncrypt, KeyInit};
    use aes::Aes256;

    let cipher = Aes256::new_from_slice(key).expect("invalid key size");
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

    result
}

#[pyfunction]
fn aes_ige_enc(py: Python<'_>, data: Vec<u8>, key: Vec<u8>, iv: Vec<u8>) -> PyResult<Py<PyBytes>> {
    let out = aes_ige_impl(&data, &key, &iv, 1);
    Ok(PyBytes::new(py, &out).into())
}

#[pyfunction]
fn aes_ige_dec(py: Python<'_>, data: Vec<u8>, key: Vec<u8>, iv: Vec<u8>) -> PyResult<Py<PyBytes>> {
    let out = aes_ige_impl(&data, &key, &iv, 0);
    Ok(PyBytes::new(py, &out).into())
}

#[pyfunction]
fn aes_ige_enc_raw(data: Vec<u8>, key: Vec<u8>, iv: Vec<u8>) -> PyResult<Vec<u8>> {
    Ok(aes_ige_impl(&data, &key, &iv, 1))
}

#[pyfunction]
fn aes_ige_dec_raw(data: Vec<u8>, key: Vec<u8>, iv: Vec<u8>) -> PyResult<Vec<u8>> {
    Ok(aes_ige_impl(&data, &key, &iv, 0))
}

#[pyfunction]
fn cut(py: Python<'_>, data: Vec<u8>, offset: usize, length: usize) -> PyResult<Py<PyBytes>> {
    let end = (offset + length).min(data.len());
    Ok(PyBytes::new(py, &data[offset..end]).into())
}

#[pyfunction]
fn pack(py: Python<'_>, parts: Vec<Vec<u8>>) -> PyResult<Py<PyBytes>> {
    let mut out = Vec::new();
    for p in parts {
        out.extend_from_slice(&p);
    }
    Ok(PyBytes::new(py, &out).into())
}

#[pymodule]
fn ext(m: &PyModule) -> PyResult<()> {
    apply_bootstrap();
    m.add_function(wrap_pyfunction!(load_schema, m)?)?;
    m.add_function(wrap_pyfunction!(schema_info, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_method, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_constructor, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_enc, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_enc_raw, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec_raw, m)?)?;
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
        let enc = aes_ige_impl(&plain, &key, &iv, 1);
        let dec = aes_ige_impl(&enc, &key, &iv, 0);
        assert_eq!(&dec, &plain);
    }
}
