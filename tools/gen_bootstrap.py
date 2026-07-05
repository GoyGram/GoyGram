import json, sys, re, os

VECTOR_RE = re.compile(r"^Vector<(.*)>$")
FLAG_RE = re.compile(r"^flags\.(\d+)\?(.+)$")

def _parse_field_type(raw):
    raw = raw.strip()
    m = VECTOR_RE.match(raw)
    if m:
        inner = _parse_field_type(m.group(1))
        return {"type": "Vector", "is_vector": True, "vector_inner": inner["type"]}
    m = FLAG_RE.match(raw)
    if m:
        bit = int(m.group(1))
        inner_raw = m.group(2)
        inner = _parse_field_type(inner_raw)
        inner["flag_bit"] = bit
        return inner
    if raw in {"true", "True"}:
        return {"type": "true", "is_bare": True}
    return {"type": raw}

def _parse_fields(fields_str):
    result = []
    has_flags = False
    tokens = fields_str.strip().split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if ":" not in token:
            i += 1
            continue
        name, type_str = token.split(":", 1)
        field = _parse_field_type(type_str)
        field["name"] = name
        field.setdefault("is_bare", False)
        field.setdefault("is_vector", False)
        field.setdefault("vector_inner", None)
        field.setdefault("flag_bit", None)
        if type_str == "#":
            has_flags = True
        result.append(field)
        i += 1
    return result, has_flags

api_tl_path = sys.argv[1]
api_tl_text = open(api_tl_path).read()

mtproto_tl_path = sys.argv[2] if len(sys.argv) > 2 else None
mtproto_text = ""
if mtproto_tl_path and os.path.exists(mtproto_tl_path):
    mtproto_text = open(mtproto_tl_path).read()

text = mtproto_text + "\n" + api_tl_text

BOOTSTRAP_METHODS = {
    "req_pq_multi", "req_DH_params", "set_client_DH_params",
    "auth.sendCode", "auth.signIn", "auth.signUp", "auth.checkPassword", "auth.logOut",
    "account.getPassword", "account.updateStatus", "updates.getState",
    "msgs_ack", "help.getConfig", "help.getNearestDc",
    "initConnection", "invokeWithLayer",
    "auth.exportLoginToken", "auth.importLoginToken",
    "auth.requestPasswordRecovery",
    "rpc_drop_answer", "msgs_state_req",
}

BOOTSTRAP_CTORS = {
    "inputPeerEmpty", "inputPeerSelf", "inputPeerUser", "inputPeerChat",
    "inputPeerChannel", "inputUser", "inputUserSelf", "inputChannel",
    "inputReplyToMessage", "p_q_inner_data", "p_q_inner_data_dc",
    "client_DH_inner_data", "inputCheckPasswordSRP", "inputCheckPasswordEmpty",
    "codeSettings", "resPQ", "server_DH_params_ok", "server_DH_inner_data",
    "dh_gen_ok", "dh_gen_retry", "dh_gen_fail",
    "rpc_result", "gzip_packed", "msg_container",
    "emailVerificationCode", "emailVerificationGoogle",
    "inputClientProxy",
}

methods = {}
constructors = {}

for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("//"):
        if "---functions---" in line or "---types---" in line:
            continue
        continue

    line_unsc = line.rstrip(";")
    m = re.match(
        r"^([A-Za-z0-9_.]+)#([0-9a-fA-F]+)\s*(.*?)\s*=\s*.+$",
        line_unsc,
    )
    if not m:
        continue

    name, cid_hex, rest = m.group(1), m.group(2), m.group(3)
    rest = re.sub(r"\{[^}]*\}", "", rest)
    cid = int(cid_hex, 16)

    if name in BOOTSTRAP_CTORS and name not in constructors:
        fields, has_flags = _parse_fields(rest)
        constructors[name] = {"cid": cid, "fields": fields, "has_flags": has_flags}
    if name in BOOTSTRAP_METHODS and name not in methods:
        fields, has_flags = _parse_fields(rest)
        methods[name] = {"cid": cid, "fields": fields, "has_flags": has_flags}

schema = {"methods": methods, "constructors": constructors}
print(json.dumps(schema, indent=2))
