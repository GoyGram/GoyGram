// CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
#[cfg(any(target_arch = "aarch64", test))]
static AES_SBOX: [u8; 256] = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16,
];

#[cfg(any(target_arch = "aarch64", test))]
const fn aes_xtime(x: u8) -> u8 {
    (x << 1) ^ (0x1b & 0u8.wrapping_sub(x >> 7))
}

#[cfg(any(target_arch = "aarch64", test))]
fn aes256_round_keys(key: &[u8; 32]) -> [u8; 240] {
    let mut w = [0u8; 240];
    w[..32].copy_from_slice(key);

    let mut rcon: u8 = 1;
    let mut i = 8;
    while i < 60 {
        let p = 4 * i;
        let mut t = [w[p - 4], w[p - 3], w[p - 2], w[p - 1]];
        if i % 8 == 0 {
            t = [
                AES_SBOX[t[1] as usize] ^ rcon,
                AES_SBOX[t[2] as usize],
                AES_SBOX[t[3] as usize],
                AES_SBOX[t[0] as usize],
            ];
            rcon = aes_xtime(rcon);
        } else if i % 8 == 4 {
            t = [
                AES_SBOX[t[0] as usize],
                AES_SBOX[t[1] as usize],
                AES_SBOX[t[2] as usize],
                AES_SBOX[t[3] as usize],
            ];
        }
        let q = 4 * (i - 8);
        w[p] = w[q] ^ t[0];
        w[p + 1] = w[q + 1] ^ t[1];
        w[p + 2] = w[q + 2] ^ t[2];
        w[p + 3] = w[q + 3] ^ t[3];
        i += 1;
    }
    w
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

#[cfg(target_arch = "aarch64")]
mod arm64 {
    use super::aes256_round_keys;
    use core::arch::aarch64::*;

    #[inline]
    #[target_feature(enable = "aes", enable = "neon")]
    unsafe fn enc_block(mut s: uint8x16_t, k: &[uint8x16_t; 15]) -> uint8x16_t {
        let mut i = 0;
        while i < 13 {
            s = vaesmcq_u8(vaeseq_u8(s, k[i]));
            i += 1;
        }
        veorq_u8(vaeseq_u8(s, k[13]), k[14])
    }

    #[inline]
    #[target_feature(enable = "aes", enable = "neon")]
    unsafe fn dec_block(mut s: uint8x16_t, k: &[uint8x16_t; 15]) -> uint8x16_t {
        let mut i = 0;
        while i < 13 {
            s = vaesimcq_u8(vaesdq_u8(s, k[i]));
            i += 1;
        }
        veorq_u8(vaesdq_u8(s, k[13]), k[14])
    }

    #[target_feature(enable = "aes", enable = "neon")]
    unsafe fn ige(data: &[u8], key: &[u8; 32], iv: &[u8; 32], direction: u8) -> Vec<u8> {
        let bytes = aes256_round_keys(key);
        let mut enc: [uint8x16_t; 15] = core::mem::zeroed();
        let mut i = 0;
        while i < 15 {
            enc[i] = vld1q_u8(bytes.as_ptr().add(i * 16));
            i += 1;
        }

        let mut dec = enc;
        if direction == 0 {
            let mut j = 1;
            while j < 14 {
                dec[j] = vaesimcq_u8(dec[j]);
                j += 1;
            }
            dec.reverse();
        }
        let keys: &[uint8x16_t; 15] = if direction == 0 { &dec } else { &enc };

        let mut result = vec![0u8; data.len()];
        let mut x = vld1q_u8(if direction == 0 { iv.as_ptr().add(16) } else { iv.as_ptr() });
        let mut y = vld1q_u8(if direction == 0 { iv.as_ptr() } else { iv.as_ptr().add(16) });
        let mut off = 0usize;
        while off < data.len() {
            let m = vld1q_u8(data.as_ptr().add(off));
            let t = veorq_u8(m, x);
            let out = if direction == 0 { dec_block(t, keys) } else { enc_block(t, keys) };
            let out = veorq_u8(out, y);
            vst1q_u8(result.as_mut_ptr().add(off), out);
            x = out;
            y = m;
            off += 16;
        }
        result
    }

    pub(super) unsafe fn run(data: &[u8], key: &[u8; 32], iv: &[u8; 32], direction: u8) -> Vec<u8> {
        ige(data, key, iv, direction)
    }
}

pub(crate) fn has_hardware_aes() -> bool {
    #[cfg(target_arch = "x86_64")]
    {
        std::arch::is_x86_feature_detected!("aes") && std::arch::is_x86_feature_detected!("sse2")
    }
    #[cfg(target_arch = "aarch64")]
    {
        std::arch::is_aarch64_feature_detected!("aes")
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    {
        false
    }
}

pub(crate) fn aes_ige_impl(data: &[u8], key: &[u8], iv: &[u8], direction: u8) -> Result<Vec<u8>, String> {
    if data.len() % 16 != 0 {
        return Err("AES-IGE data length must be a multiple of 16".to_string());
    }
    if key.len() != 32 {
        return Err("AES-IGE key must be 32 bytes".to_string());
    }
    if iv.len() != 32 {
        return Err("AES-IGE IV must be 32 bytes".to_string());
    }

    #[cfg(target_arch = "x86_64")]
    if std::arch::is_x86_feature_detected!("aes") && std::arch::is_x86_feature_detected!("sse2") {
        let mut key_arr = [0u8; 32];
        let mut iv_arr = [0u8; 32];
        key_arr.copy_from_slice(key);
        iv_arr.copy_from_slice(iv);
        return Ok(unsafe { aes_ige_x86(data, &key_arr, &iv_arr, direction) });
    }

    #[cfg(target_arch = "aarch64")]
    if std::arch::is_aarch64_feature_detected!("aes") {
        let mut key_arr = [0u8; 32];
        let mut iv_arr = [0u8; 32];
        key_arr.copy_from_slice(key);
        iv_arr.copy_from_slice(iv);
        return Ok(unsafe { arm64::run(data, &key_arr, &iv_arr, direction) });
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

#[cfg(test)]
mod tests {
    use super::{aes256_round_keys, aes_ige_impl};

    const KEY: [u8; 32] = [
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e,
        0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d,
        0x1e, 0x1f,
    ];
    const IV: [u8; 32] = [
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e,
        0x2f, 0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d,
        0x3e, 0x3f,
    ];

    fn plain() -> Vec<u8> {
        (0x00u8..0x40).collect()
    }

    const EXPECTED: &str = "42e66e1a756cccf5b27acc47523ad074ee39bf54e3db37bbdf415df6b400fca977f708327c9e9341cc3dc8efd31e76463daa65b1f0d0252f790d77f1824a662c";

    #[test]
    fn ige_known_answer() {
        let enc = aes_ige_impl(&plain(), &KEY, &IV, 1).unwrap();
        assert_eq!(hex::encode(&enc), EXPECTED);
        let dec = aes_ige_impl(&enc, &KEY, &IV, 0).unwrap();
        assert_eq!(dec, plain());
    }

    #[test]
    fn ige_roundtrip() {
        let key = [0u8; 32];
        let iv = [1u8; 32];
        let plain = [42u8; 64];
        let enc = aes_ige_impl(&plain, &key, &iv, 1).unwrap();
        let dec = aes_ige_impl(&enc, &key, &iv, 0).unwrap();
        assert_eq!(&dec, &plain);
    }

    #[cfg(target_arch = "x86_64")]
    #[test]
    fn portable_schedule_matches_aesni() {
        if !std::arch::is_x86_feature_detected!("aes") {
            return;
        }
        for seed in 0u8..=255 {
            let mut key = [0u8; 32];
            for (i, b) in key.iter_mut().enumerate() {
                *b = seed.wrapping_mul(37).wrapping_add(i as u8);
            }
            let hw = unsafe { super::ige_expand_keys(&key) };
            let mut hw_bytes = [0u8; 240];
            unsafe { std::ptr::copy_nonoverlapping(hw.as_ptr() as *const u8, hw_bytes.as_mut_ptr(), 240) };
            assert_eq!(aes256_round_keys(&key), hw_bytes, "round keys diverged for seed {seed}");
        }
    }
}
