# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.

import re



class GoyGramError(Exception):
    pass


class TransportError(GoyGramError):
    pass


class ConnectionClosedError(TransportError):
    pass


class ProxyError(TransportError):
    pass


class RPCError(GoyGramError):

    def __init__(self, code: int, message: str) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code}, message={self.message!r})"



class SeeOtherError(RPCError):
    pass



class BadRequestError(RPCError):
    pass


class FloodWaitError(BadRequestError):

    def __init__(self, code: int, message: str, seconds: int) -> None:
        super().__init__(code, message)
        self.seconds = seconds

    def __str__(self) -> str:
        return f"[{self.code}] FLOOD_WAIT_{self.seconds}"


class UserRestrictedError(BadRequestError):
    pass


class UserBannedError(BadRequestError):
    pass


class PhoneCodeInvalidError(BadRequestError):
    pass


class PhoneCodeExpiredError(BadRequestError):
    pass


class MessageTooLongError(BadRequestError):
    pass


class MessageNotModifiedError(BadRequestError):
    pass


class MessageIdInvalidError(BadRequestError):
    pass


class PeerIdInvalidError(BadRequestError):
    pass


class UsernameInvalidError(BadRequestError):
    pass


class UsernameNotOccupiedError(BadRequestError):
    pass


class ChatAdminRequiredError(BadRequestError):
    pass


class ChatNotModifiedError(BadRequestError):
    pass


class EntityBoundsInvalidError(BadRequestError):
    pass


class ButtonDataInvalidError(BadRequestError):
    pass


class InputConstructorInvalidError(BadRequestError):
    pass


class InputMethodInvalidError(BadRequestError):
    pass


class FileReferenceExpiredError(BadRequestError):
    pass


class FilePartInvalidError(BadRequestError):
    pass


class PersistentTimestampOutdatedError(BadRequestError):
    pass


class UsersTooFewError(BadRequestError):
    pass


class UsersTooMuchError(BadRequestError):
    pass


class UserAlreadyParticipantError(BadRequestError):
    pass


class UserNotParticipantError(BadRequestError):
    pass


class PhotoSaveFileInvalidError(BadRequestError):
    pass


class ImageProcessFailedError(BadRequestError):
    pass



class UnauthorizedError(RPCError):
    pass


class AuthKeyUnregisteredError(UnauthorizedError):
    pass


class SessionPasswordNeededError(UnauthorizedError):
    pass


class AuthKeyInvalidError(UnauthorizedError):
    pass


class PhoneNumberUnoccupiedError(UnauthorizedError):
    pass


class PhoneNumberInvalidError(UnauthorizedError):
    pass


class PhoneCodeHashEmptyError(UnauthorizedError):
    pass



class ForbiddenError(RPCError):
    pass


class ChatWriteForbiddenError(ForbiddenError):
    pass


class UserBannedInChannelError(ForbiddenError):
    pass


class UserPrivacyRestrictedError(ForbiddenError):
    pass


class UserChannelsTooMuchError(ForbiddenError):
    pass


class UserKickedError(ForbiddenError):
    pass


class MessageDeleteForbiddenError(ForbiddenError):
    pass


class PollVoteRequiredError(ForbiddenError):
    pass


class BroadcastForbiddenError(ForbiddenError):
    pass


class ChannelPrivateError(ForbiddenError):
    pass



class NotFoundError(RPCError):
    pass


class ChannelNotFoundError(NotFoundError):
    pass


class ChatNotFoundError(NotFoundError):
    pass


class UserNotFoundError(NotFoundError):
    pass


class MessageNotFoundError(NotFoundError):
    pass


class FileNotFoundError(NotFoundError):
    pass



class NotAcceptableError(RPCError):
    pass


class ChannelTooLargeError(NotAcceptableError):
    pass


class FreshChangeAdminsForbiddenError(NotAcceptableError):
    pass


class ChannelIdInvalidError(NotAcceptableError):
    pass


class FilerefUpgradeNeededError(NotAcceptableError):
    pass



class InternalServerError(RPCError):
    pass


class RpcCallFailError(InternalServerError):
    pass


class RpcMcGetFailError(InternalServerError):
    pass


class ApiCallError(InternalServerError):
    pass


class TimeoutError(GoyGramError):
    pass


class AuthError(GoyGramError):
    pass


class CodecError(GoyGramError):
    pass


class RustExtError(GoyGramError):
    pass



_ERROR_PATTERNS: list[tuple[str, type[RPCError]]] = [
    (r"^FLOOD_WAIT_(\d+)$", None),  # special handling — extracts seconds

    ("USER_RESTRICTED", UserRestrictedError),
    ("USER_BANNED", UserBannedError),
    ("USER_DEACTIVATED", UserBannedError),
    ("USER_DELETED", UserBannedError),
    ("PHONE_CODE_INVALID", PhoneCodeInvalidError),
    ("PHONE_CODE_EXPIRED", PhoneCodeExpiredError),
    ("PHONE_CODE_EMPTY", PhoneCodeInvalidError),
    ("MESSAGE_TOO_LONG", MessageTooLongError),
    ("MESSAGE_NOT_MODIFIED", MessageNotModifiedError),
    ("MESSAGE_ID_INVALID", MessageIdInvalidError),
    ("PEER_ID_INVALID", PeerIdInvalidError),
    ("USERNAME_INVALID", UsernameInvalidError),
    ("USERNAME_NOT_OCCUPIED", UsernameNotOccupiedError),
    ("CHAT_ADMIN_REQUIRED", ChatAdminRequiredError),
    ("CHAT_NOT_MODIFIED", ChatNotModifiedError),
    ("ENTITY_BOUNDS_INVALID", EntityBoundsInvalidError),
    ("BUTTON_DATA_INVALID", ButtonDataInvalidError),
    ("INPUT_CONSTRUCTOR_INVALID", InputConstructorInvalidError),
    ("INPUT_METHOD_INVALID", InputMethodInvalidError),
    ("INPUT_FETCH_FAIL", InputConstructorInvalidError),
    ("INPUT_FETCH_ERROR", InputConstructorInvalidError),
    ("FILE_REFERENCE_EXPIRED", FileReferenceExpiredError),
    ("FILE_REFERENCE_EMPTY", FileReferenceExpiredError),
    ("FILE_REFERENCE_INVALID", FileReferenceExpiredError),
    ("FILE_PART_SIZE_INVALID", FilePartInvalidError),
    ("FILE_PART_SIZE_CHANGED", FilePartInvalidError),
    ("FILE_PART_MISSING", FilePartInvalidError),
    ("PERSISTENT_TIMESTAMP_OUTDATED", PersistentTimestampOutdatedError),
    ("PERSISTENT_TIMESTAMP_INVALID", PersistentTimestampOutdatedError),
    ("USERS_TOO_FEW", UsersTooFewError),
    ("USERS_TOO_MUCH", UsersTooMuchError),
    ("USER_ALREADY_PARTICIPANT", UserAlreadyParticipantError),
    ("USER_NOT_PARTICIPANT", UserNotParticipantError),
    ("PHOTO_SAVE_FILE_INVALID", PhotoSaveFileInvalidError),
    ("IMAGE_PROCESS_FAILED", ImageProcessFailedError),

    ("AUTH_KEY_UNREGISTERED", AuthKeyUnregisteredError),
    ("AUTH_KEY_INVALID", AuthKeyInvalidError),
    ("AUTH_KEY_PERM_EMPTY", AuthKeyUnregisteredError),
    ("AUTH_KEY_DUPLICATED", AuthKeyUnregisteredError),
    ("SESSION_PASSWORD_NEEDED", SessionPasswordNeededError),
    ("SESSION_REVOKED", AuthKeyUnregisteredError),
    ("SESSION_EXPIRED", AuthKeyUnregisteredError),
    ("PHONE_NUMBER_UNOCCUPIED", PhoneNumberUnoccupiedError),
    ("PHONE_NUMBER_INVALID", PhoneNumberInvalidError),
    ("PHONE_CODE_HASH_EMPTY", PhoneCodeHashEmptyError),

    ("CHAT_WRITE_FORBIDDEN", ChatWriteForbiddenError),
    ("USER_BANNED_IN_CHANNEL", UserBannedInChannelError),
    ("USER_PRIVACY_RESTRICTED", UserPrivacyRestrictedError),
    ("USER_CHANNELS_TOO_MUCH", UserChannelsTooMuchError),
    ("USER_KICKED", UserKickedError),
    ("MESSAGE_DELETE_FORBIDDEN", MessageDeleteForbiddenError),
    ("POLL_VOTE_REQUIRED", PollVoteRequiredError),
    ("BROADCAST_FORBIDDEN", BroadcastForbiddenError),
    ("CHANNEL_PRIVATE", ChannelPrivateError),
    ("CHANNEL_PUBLIC_GROUP_NA", ChannelPrivateError),
    ("RIGHT_FORBIDDEN", ForbiddenError),
    ("SENSITIVE_CHANGE_FORBIDDEN", ForbiddenError),

    ("CHANNEL_NOT_FOUND", ChannelNotFoundError),
    ("CHAT_NOT_FOUND", ChatNotFoundError),
    ("USER_NOT_FOUND", UserNotFoundError),
    ("MESSAGE_NOT_FOUND", MessageNotFoundError),
    ("FILE_NOT_FOUND", FileNotFoundError),
    ("CHANNEL_INVALID", ChannelNotFoundError),
    ("CHAT_ID_INVALID", ChatNotFoundError),

    ("CHANNEL_TOO_LARGE", ChannelTooLargeError),
    ("CHANNEL_TOO_BIG", ChannelTooLargeError),
    ("FRESH_CHANGE_ADMINS_FORBIDDEN", FreshChangeAdminsForbiddenError),
    ("CHANNEL_ID_INVALID", ChannelIdInvalidError),
    ("FILEREF_UPGRADE_NEEDED", FilerefUpgradeNeededError),

    ("RPC_CALL_FAIL", RpcCallFailError),
    ("RPC_MCGET_FAIL", RpcMcGetFailError),
    ("API_CALL_ERROR", ApiCallError),
    ("WORKER_BUSY_TOO_LONG_RETRY", InternalServerError),
    ("MSG_WAIT_FAILED", InternalServerError),

    ("PHONE_MIGRATE_", SeeOtherError),
    ("NETWORK_MIGRATE_", SeeOtherError),
    ("USER_MIGRATE_", SeeOtherError),
    ("FILE_MIGRATE_", SeeOtherError),
]


def rpc_error(code: int, message: str) -> RPCError:
    m = re.match(r"^FLOOD_WAIT_(\d+)$", message)
    if m:
        return FloodWaitError(code, message, int(m.group(1)))

    for pattern, cls in _ERROR_PATTERNS:
        if pattern in message:
            return cls(code, message)

    return _CODE_FALLBACK.get(code, RPCError)(code, message)


_CODE_FALLBACK: dict[int, type[RPCError]] = {
    303: SeeOtherError,
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    406: NotAcceptableError,
    500: InternalServerError,
}


def rpc_error_from_dict(err: dict[str, object]) -> RPCError:
    code = int(err.get("error_code", 500))
    msg = str(err.get("error_message", f"RPC code {code}"))
    return rpc_error(code, msg)
