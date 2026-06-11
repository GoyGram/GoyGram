# CopyLeft 2026 github.com/sepiol026-wq | telegram:@samsepi0l_ovf. Licensed under AGPLv3.
from __future__ import annotations

import inspect
from typing import Any

from goygram.filters import Filter, me, text


def print_methods(app: Any) -> None:
    lines: list[str] = []
    lines.append("=== GoyGram Developer Help ===")
    lines.append("• All methods are dynamically dispatched via runtime TL parsing:")
    lines.append("  - Bot API: app.<camelCase>(...) e.g. app.sendMessage(...)")
    lines.append("  - MTProto: app.mt_<namespace>_<method>(...) e.g. app.mt_messages_get_dialogs(...)")
    lines.append("  - Complex types must be pre-serialized via codec helpers")
    lines.append("• Built-in:")
    for name in sorted(x for x in dir(app) if not x.startswith("_") and callable(getattr(app, x, None))):
        if name == "help":
            sig = inspect.signature(getattr(app, name))
            lines.append(f"  - {name}{sig}")
    lines.append("• Handler decorators:")
    lines.append("  - on_msg(filt=...)     — message handler with optional filter")
    lines.append("  - on_cb(filt=...)      — callback query handler with optional filter")
    lines.append("  - on_poll(filt=...)    — poll handler with optional filter")
    lines.append("  - on_member(filt=...)  — member update handler with optional filter")
    lines.append("  - on_update(filt=...)  — catch-all handler for any event type")
    lines.append("  - on_cmd('cmd1', ...)  — command handler (shortcut for on_msg + command filter)")
    lines.append("• Filters (100+):")
    lines.append("  TEXT: text, command, regex, fullmatch, findall, finditer, split,")
    lines.append("        contains, contains_any, contains_all, startswith, endswith,")
    lines.append("        text_len, word_count, line_count, numeric, json_text, is_language")
    lines.append("  ENTITIES: has_url, has_mention, has_hashtag, has_cashtag, has_email,")
    lines.append("            has_phone, has_bold, has_italic, has_code, has_pre,")
    lines.append("            has_spoiler, has_custom_emoji, has_blockquote, has_underline,")
    lines.append("            has_strikethrough, has_text_link, has_text_mention,")
    lines.append("            has_bank_card, mentioned, has_entity('type')")
    lines.append("  MEDIA: photo, video, audio, document, sticker, animation, voice,")
    lines.append("         video_note, location, contact, venue, dice, game, invoice,")
    lines.append("         story, giveaway, media, media_group, caption, media_size,")
    lines.append("         media_duration, media_mime, media_width, media_height,")
    lines.append("         file_name, specific_media_group, album_len")
    lines.append("  CAPTION: caption_regex, caption_contains, caption_len")
    lines.append("  CHAT: private, group, supergroup, channel, forum, chat_type,")
    lines.append("        chat(id), any_chat(*ids), not_chat(*ids), topic(id)")
    lines.append("  SENDER: me, from_user(id), from_any(*ids), not_from(*ids), is_bot,")
    lines.append("          is_premium, is_verified, is_scam, is_fake, is_support,")
    lines.append("          is_contact, is_mutual_contact, lang_code('ru')")
    lines.append("  MESSAGE PROPS: edited, forwarded, reply, pinned, has_protected_content,")
    lines.append("                 has_media_spoiler, via_bot, is_topic_message, has_markup,")
    lines.append("                 has_inline_kbd, has_reply_kbd, has_web_preview, silent,")
    lines.append("                 from_offline, effect, noforwards, views, forwards,")
    lines.append("                 reaction, message_id")
    lines.append("  SERVICE: service, new_chat_members, left_chat_member, new_chat_title,")
    lines.append("           new_chat_photo, delete_chat_photo, group_created, channel_created,")
    lines.append("           migrate_to, migrate_from, pinned_msg, connected_website,")
    lines.append("           proximity_alert, video_chat_started/ended/scheduled,")
    lines.append("           message_auto_delete_timer, successful_payment, users_shared,")
    lines.append("           chat_shared, write_access_allowed, boost_added,")
    lines.append("           forum_topic_created/edited/closed/reopened,")
    lines.append("           giveaway_created/completed/winners")
    lines.append("  CALLBACK: cb_data, cb_startswith, cb_endswith, cb_contains, cb_regex,")
    lines.append("            cb_payload, cb_json, cb_kvp, cb_from, cb_chat, cb_msg,")
    lines.append("            cb_game, cb_any")
    lines.append("  POLL: poll_filter, poll_closed, poll_open, poll_question, poll_contains,")
    lines.append("        poll_regex, poll_type, poll_chat, poll_option, poll_any, poll_answer")
    lines.append("  MEMBER: member_joined, member_left, member_banned, member_unbanned,")
    lines.append("          member_promoted, member_demoted, member_restricted, member_unrestricted,")
    lines.append("          member_status, member_chat, member_user, member_by, member_self")
    lines.append("  CROSS-TYPE: update_type('msg'|'cb'|'poll'|'member'), network('bot'|'mt'),")
    lines.append("              user(id)")
    lines.append("  COMPOSITION: & | ~ ^ - (operators), all_of, any_of, none_of,")
    lines.append("               at_least, at_most, exactly, invert, if_, unless")
    lines.append("  STATEFUL: once, limit(n), every_n(n), cooldown(secs), throttled(rate, per)")
    lines.append("  UTILITY: any_filter, none_filter, func(callable), filter_data(**kw)")
    lines.append("  INTROSPECTION: filter.explain(event), filter.tree()")
    print("\n".join(lines))


__all__ = ["print_methods", "Filter", "text", "me"]
