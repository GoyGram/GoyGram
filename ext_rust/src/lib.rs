// Copyleft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
use aes::cipher::generic_array::GenericArray;
use aes::cipher::{BlockDecrypt, BlockEncrypt, KeyInit};
use aes::Aes256;
use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, Nonce};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use serde::Deserialize;
use std::collections::HashMap;
use std::sync::OnceLock;

fn pad(src: &[u8]) -> Vec<u8> {
    let n = 16 - (src.len() % 16);
    let p = if n == 0 { 16 } else { n };
    let mut out = Vec::with_capacity(src.len() + p);
    out.extend_from_slice(src);
    out.resize(src.len() + p, p as u8);
    out
}

fn unpad(src: &[u8]) -> PyResult<Vec<u8>> {
    if src.is_empty() {
        return Ok(Vec::new());
    }
    let p = *src.last().unwrap() as usize;
    if p == 0 || p > 16 || src.len() < p {
        return Err(PyValueError::new_err("bad pad"));
    }
    if src[src.len() - p..].iter().any(|b| *b as usize != p) {
        return Err(PyValueError::new_err("bad pad"));
    }
    Ok(src[..src.len() - p].to_vec())
}

fn chk(key: &[u8], iv: &[u8], data: &[u8]) -> PyResult<()> {
    if key.len() != 32 {
        return Err(PyValueError::new_err("key must be 32 bytes"));
    }
    if iv.len() != 32 {
        return Err(PyValueError::new_err("iv must be 32 bytes"));
    }
    if data.len() % 16 != 0 {
        return Err(PyValueError::new_err("data must be multiple of 16"));
    }
    Ok(())
}

fn enc_raw(key: &[u8], iv: &[u8], data: &[u8]) -> PyResult<Vec<u8>> {
    chk(key, iv, data)?;
    let aes = Aes256::new_from_slice(key).map_err(|_| PyValueError::new_err("bad key"))?;
    let mut x = iv[..16].to_vec();
    let mut y = iv[16..].to_vec();
    let mut out = Vec::with_capacity(data.len());
    for blk in data.chunks_exact(16) {
        let mut tmp = [0u8; 16];
        for i in 0..16 {
            tmp[i] = blk[i] ^ x[i];
        }
        let mut ga = GenericArray::clone_from_slice(&tmp);
        aes.encrypt_block(&mut ga);
        let mut c = [0u8; 16];
        for i in 0..16 {
            c[i] = ga[i] ^ y[i];
        }
        x.copy_from_slice(&c);
        y.copy_from_slice(blk);
        out.extend_from_slice(&c);
    }
    Ok(out)
}

fn dec_raw(key: &[u8], iv: &[u8], data: &[u8]) -> PyResult<Vec<u8>> {
    chk(key, iv, data)?;
    let aes = Aes256::new_from_slice(key).map_err(|_| PyValueError::new_err("bad key"))?;
    let mut x = iv[..16].to_vec();
    let mut y = iv[16..].to_vec();
    let mut out = Vec::with_capacity(data.len());
    for blk in data.chunks_exact(16) {
        let mut tmp = [0u8; 16];
        for i in 0..16 {
            tmp[i] = blk[i] ^ y[i];
        }
        let mut ga = GenericArray::clone_from_slice(&tmp);
        aes.decrypt_block(&mut ga);
        let mut p = [0u8; 16];
        for i in 0..16 {
            p[i] = ga[i] ^ x[i];
        }
        x.copy_from_slice(blk);
        y.copy_from_slice(&p);
        out.extend_from_slice(&p);
    }
    Ok(out)
}

#[pyfunction]
fn aes_ige_enc(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    let raw = pad(data);
    enc_raw(key, iv, &raw)
}

#[pyfunction]
fn aes_ige_dec(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    let raw = dec_raw(key, iv, data)?;
    unpad(&raw)
}

#[pyfunction]
fn aes_ige_enc_raw(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    enc_raw(key, iv, data)
}

#[pyfunction]
fn aes_ige_dec_raw(data: &[u8], key: &[u8], iv: &[u8]) -> PyResult<Vec<u8>> {
    dec_raw(key, iv, data)
}

#[pyfunction]
fn cut(py: Python<'_>, buf: &[u8]) -> PyResult<(Vec<Py<PyBytes>>, Py<PyBytes>)> {
    let mut i = 0usize;
    let mut out = Vec::new();
    while i + 4 <= buf.len() {
        let n = u32::from_le_bytes([buf[i], buf[i + 1], buf[i + 2], buf[i + 3]]) as usize;
        if n == 0 {
            return Err(PyValueError::new_err("zero frame"));
        }
        if i + 4 + n > buf.len() {
            break;
        }
        out.push(PyBytes::new(py, &buf[i + 4..i + 4 + n]).into());
        i += 4 + n;
    }
    Ok((out, PyBytes::new(py, &buf[i..]).into()))
}

#[pyfunction]
fn pack(data: &[u8]) -> Vec<u8> {
    let mut out = Vec::with_capacity(data.len() + 4);
    out.extend_from_slice(&(data.len() as u32).to_le_bytes());
    out.extend_from_slice(data);
    out
}

#[pyfunction]
fn aes_gcm_encrypt(py: Python<'_>, key: &[u8], nonce: &[u8], plaintext: &[u8], aad: &[u8]) -> PyResult<Py<PyBytes>> {
    if key.len() != 32 {
        return Err(PyValueError::new_err("key must be 32 bytes"));
    }
    if nonce.len() != 12 {
        return Err(PyValueError::new_err("nonce must be 12 bytes"));
    }
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|_| PyValueError::new_err("bad key"))?;
    let n = Nonce::from_slice(nonce);
    let ct = cipher
        .encrypt(n, aes_gcm::aead::Payload { msg: plaintext, aad })
        .map_err(|_| PyValueError::new_err("encryption failed"))?;
    Ok(PyBytes::new(py, &ct).into())
}

#[pyfunction]
fn aes_gcm_decrypt(py: Python<'_>, key: &[u8], nonce: &[u8], ciphertext: &[u8], aad: &[u8]) -> PyResult<Py<PyBytes>> {
    if key.len() != 32 {
        return Err(PyValueError::new_err("key must be 32 bytes"));
    }
    if nonce.len() != 12 {
        return Err(PyValueError::new_err("nonce must be 12 bytes"));
    }
    let cipher = Aes256Gcm::new_from_slice(key)
        .map_err(|_| PyValueError::new_err("bad key"))?;
    let n = Nonce::from_slice(nonce);
    let pt = cipher
        .decrypt(n, aes_gcm::aead::Payload { msg: ciphertext, aad })
        .map_err(|_| PyValueError::new_err("decryption failed (wrong key or corrupted data)"))?;
    Ok(PyBytes::new(py, &pt).into())
}

#[derive(Debug, Clone, Deserialize)]
struct TlFieldDef {
    name: String,
    #[serde(rename = "type")]
    field_type: String,
    #[serde(default)]
    flag_bit: Option<u32>,
    #[serde(default)]
    is_bare: bool,
    #[serde(default)]
    is_vector: bool,
    #[serde(default)]
    vector_inner: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
struct TlMethodDef {
    cid: u32,
    fields: Vec<TlFieldDef>,
    #[serde(default)]
    has_flags: bool,
}

#[derive(Debug, Clone)]
struct TlMethod {
    cid: u32,
    fields: Vec<TlFieldDef>,
    has_flags: bool,
}

static SCHEMA: OnceLock<HashMap<String, TlMethod>> = OnceLock::new();

fn get_schema() -> PyResult<&'static HashMap<String, TlMethod>> {
    SCHEMA.get().ok_or_else(|| PyValueError::new_err("TL schema not loaded; call load_schema first"))
}

#[pyfunction]
fn load_schema(schema_json: &str) -> PyResult<()> {
    let raw: HashMap<String, TlMethodDef> = serde_json::from_str(schema_json)
        .map_err(|e| PyValueError::new_err(format!("failed to parse schema JSON: {}", e)))?;
    let mut methods = HashMap::new();
    for (name, def) in raw {
        methods.insert(name, TlMethod {
            cid: def.cid,
            fields: def.fields,
            has_flags: def.has_flags,
        });
    }
    SCHEMA.set(methods).map_err(|_| PyValueError::new_err("schema already loaded"))?;
    Ok(())
}

fn tl_bytes_raw(data: &[u8]) -> Vec<u8> {
    let n = data.len();
    let mut out = Vec::new();
    if n < 254 {
        out.push(n as u8);
        out.extend_from_slice(data);
    } else {
        out.push(254u8);
        out.extend_from_slice(&(n as u32).to_le_bytes()[..3]);
        out.extend_from_slice(data);
    }
    let pad = (4 - (out.len() % 4)) % 4;
    out.resize(out.len() + pad, 0);
    out
}

fn hex_to_bytes(hex: &str) -> PyResult<Vec<u8>> {
    let hex = hex.trim();
    if hex.len() % 2 != 0 {
        return Err(PyValueError::new_err("hex string must have even length"));
    }
    (0..hex.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&hex[i..i + 2], 16)
            .map_err(|e| PyValueError::new_err(format!("invalid hex: {}", e))))
        .collect()
}

fn serialize_value(field: &TlFieldDef, val: &serde_json::Value) -> PyResult<Vec<u8>> {
    let ft = &field.field_type;
    if field.is_bare && ft == "true" {
        return Ok(Vec::new());
    }
    if field.is_vector {
        let inner = field.vector_inner.as_deref().unwrap_or("int");
        let arr = val.as_array().ok_or_else(|| {
            PyValueError::new_err(format!("field {} expects an array", field.name))
        })?;
        let mut out = Vec::new();
        out.extend_from_slice(&0x1cb5c415u32.to_le_bytes());
        out.extend_from_slice(&(arr.len() as i32).to_le_bytes());
        for item in arr {
            let item_field = TlFieldDef {
                name: String::new(),
                field_type: inner.to_string(),
                flag_bit: None,
                is_bare: false,
                is_vector: false,
                vector_inner: None,
            };
            out.extend(serialize_value(&item_field, item)?);
        }
        return Ok(out);
    }
    match ft.as_str() {
        "int" | "Int" => {
            let v = val.as_i64().ok_or_else(|| PyValueError::new_err(format!("field {} expects int", field.name)))?;
            Ok((v as i32).to_le_bytes().to_vec())
        }
        "uint" | "UInt" => {
            let v = val.as_u64().ok_or_else(|| PyValueError::new_err(format!("field {} expects uint", field.name)))?;
            Ok((v as u32).to_le_bytes().to_vec())
        }
        "long" | "Long" => {
            if let Some(s) = val.as_str() {
                let v: i64 = s.parse().map_err(|_| PyValueError::new_err(format!("field {} invalid long string", field.name)))?;
                return Ok(v.to_le_bytes().to_vec());
            }
            let v = val.as_i64().ok_or_else(|| PyValueError::new_err(format!("field {} expects long", field.name)))?;
            Ok(v.to_le_bytes().to_vec())
        }
        "double" | "Double" => {
            let v = val.as_f64().ok_or_else(|| PyValueError::new_err(format!("field {} expects double", field.name)))?;
            Ok(v.to_le_bytes().to_vec())
        }
        "string" | "String" => {
            let s = val.as_str().unwrap_or("");
            Ok(tl_bytes_raw(s.as_bytes()))
        }
        "bytes" | "Bytes" => {
            let s = val.as_str().ok_or_else(|| PyValueError::new_err(format!("field {} expects hex-encoded bytes", field.name)))?;
            let raw = hex_to_bytes(s)?;
            Ok(tl_bytes_raw(&raw))
        }
        "int128" => {
            let s = val.as_str().ok_or_else(|| PyValueError::new_err(format!("field {} expects hex int128", field.name)))?;
            let raw = hex_to_bytes(s)?;
            if raw.len() != 16 {
                return Err(PyValueError::new_err(format!("field {} int128 must be 16 bytes", field.name)));
            }
            Ok(raw)
        }
        "int256" => {
            let s = val.as_str().ok_or_else(|| PyValueError::new_err(format!("field {} expects hex int256", field.name)))?;
            let raw = hex_to_bytes(s)?;
            if raw.len() != 32 {
                return Err(PyValueError::new_err(format!("field {} int256 must be 32 bytes", field.name)));
            }
            Ok(raw)
        }
        "Bool" | "bool" => {
            let v = val.as_bool().unwrap_or(false);
            Ok(if v { 0x997275b5u32.to_le_bytes().to_vec() } else { 0xbc799737u32.to_le_bytes().to_vec() })
        }
        "#" => {
            let v = val.as_i64().unwrap_or(0);
            Ok((v as i32).to_le_bytes().to_vec())
        }
        _ => {
            let s = val.as_str().ok_or_else(|| {
                PyValueError::new_err(format!("field {} type {} expects hex-encoded bytes string", field.name, ft))
            })?;
            hex_to_bytes(s)
        }
    }
}

fn compute_flags(fields: &[TlFieldDef], args: &serde_json::Map<String, serde_json::Value>) -> i32 {
    let mut flags: i32 = 0;
    for field in fields {
        if let Some(bit) = field.flag_bit {
            if let Some(val) = args.get(&field.name) {
                if field.is_bare && field.field_type == "true" {
                    if val.as_bool().unwrap_or(false) {
                        flags |= 1 << bit;
                    }
                } else {
                    flags |= 1 << bit;
                }
            }
        }
    }
    flags
}

fn serialize_method_impl(name: &str, args_json: &str) -> PyResult<Vec<u8>> {
    let schema = get_schema()?;
    let method = schema.get(name).ok_or_else(|| {
        PyValueError::new_err(format!("unknown TL method: {}", name))
    })?;
    let args: serde_json::Value = serde_json::from_str(args_json)
        .map_err(|e| PyValueError::new_err(format!("invalid args JSON: {}", e)))?;
    let args_map = args.as_object().ok_or_else(|| {
        PyValueError::new_err("args must be a JSON object")
    })?;

    let mut out = Vec::new();
    out.extend_from_slice(&method.cid.to_le_bytes());

    let mut flags_val: Option<i32> = None;
    if method.has_flags {
        flags_val = Some(compute_flags(&method.fields, args_map));
    }

    let mut added_flags = false;
    for field in &method.fields {
        if field.field_type == "#" && method.has_flags {
            if let Some(f) = flags_val {
                out.extend_from_slice(&f.to_le_bytes());
                added_flags = true;
            }
            continue;
        }
        if field.flag_bit.is_some() {
            if let Some(f) = flags_val {
                if (f & (1 << field.flag_bit.unwrap())) == 0 {
                    continue;
                }
            }
            if let Some(val) = args_map.get(&field.name) {
                out.extend(serialize_value(field, val)?);
            }
            continue;
        }
        if let Some(val) = args_map.get(&field.name) {
            out.extend(serialize_value(field, val)?);
        } else if field.field_type == "#" {
            if !added_flags {
                if let Some(f) = flags_val {
                    out.extend_from_slice(&f.to_le_bytes());
                } else {
                    out.extend_from_slice(&0i32.to_le_bytes());
                }
                added_flags = true;
            }
        }
    }
    Ok(out)
}

#[pyfunction]
fn serialize_method(py: Python<'_>, name: &str, args_json: &str) -> PyResult<Py<PyBytes>> {
    let data = serialize_method_impl(name, args_json)?;
    Ok(PyBytes::new(py, &data).into())
}

#[pyfunction]
fn tl_method_exists(name: &str) -> PyResult<bool> {
    let schema = get_schema()?;
    Ok(schema.contains_key(name))
}

#[pyfunction]
fn schema_loaded() -> bool {
    SCHEMA.get().is_some()
}

#[pymodule]
fn ext(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(aes_ige_enc, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_enc_raw, m)?)?;
    m.add_function(wrap_pyfunction!(aes_ige_dec_raw, m)?)?;
    m.add_function(wrap_pyfunction!(aes_gcm_encrypt, m)?)?;
    m.add_function(wrap_pyfunction!(aes_gcm_decrypt, m)?)?;
    m.add_function(wrap_pyfunction!(cut, m)?)?;
    m.add_function(wrap_pyfunction!(pack, m)?)?;
    m.add_function(wrap_pyfunction!(load_schema, m)?)?;
    m.add_function(wrap_pyfunction!(serialize_method, m)?)?;
    m.add_function(wrap_pyfunction!(tl_method_exists, m)?)?;
    m.add_function(wrap_pyfunction!(schema_loaded, m)?)?;
    Ok(())
}
