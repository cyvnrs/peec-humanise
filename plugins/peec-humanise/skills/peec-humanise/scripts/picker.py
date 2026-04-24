#!/usr/bin/env python3
"""
peec-humanise interactive picker.
Usage: picker.py <input.json> <output.json>

Input shape:
  {"project_id": str, "items": [ {prompt_id, topic_id, topic_name, tag_ids, before, after, alt?}, ... ]}

Output shape:
  {"project_id": str, "accepted": [ {prompt_id, topic_id, tag_ids, before, selected_text, selection_mode}, ... ]}
"""
import curses
import json
import os
import sys


STATUS_NONE = "PENDING"
STATUS_AFTER = "ACCEPT_AFTER"
STATUS_ALT = "ACCEPT_ALT"
STATUS_REJECT = "REJECT"


def run_curses(stdscr, items):
    curses.curs_set(0)
    stdscr.nodelay(False)
    try:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_RED, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_CYAN, -1)
    except curses.error:
        pass

    statuses = [STATUS_NONE] * len(items)
    show_alt = [False] * len(items)
    cursor = 0
    submit_idx = len(items)
    scroll = 0

    def color(n):
        try:
            return curses.color_pair(n)
        except curses.error:
            return curses.A_NORMAL

    while True:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        list_h = max(5, h - 7)

        if cursor < scroll:
            scroll = cursor
        if cursor >= scroll + list_h:
            scroll = cursor - list_h + 1

        header = " peec-humanise   up/down move   y accept   a use alt   n reject   tab toggle   enter submit   q quit "
        stdscr.addnstr(0, 0, header[: w - 1].ljust(w - 1), w - 1, curses.A_REVERSE)

        for row_i in range(list_h):
            i = scroll + row_i
            y = 1 + row_i
            if i > submit_idx:
                break
            is_cursor = i == cursor

            if i == submit_idx:
                accepted = sum(1 for s in statuses if s in (STATUS_AFTER, STATUS_ALT))
                prefix = "> " if is_cursor else "  "
                label = f"{prefix}[ submit {accepted} accepted to peec ]"
                attr = curses.A_BOLD if is_cursor else curses.A_NORMAL
                if accepted > 0:
                    attr |= color(1)
                stdscr.addnstr(y, 0, label[: w - 1], w - 1, attr)
                continue

            item = items[i]
            st = statuses[i]
            mark = {
                STATUS_NONE: "[ ]",
                STATUS_AFTER: "[y]",
                STATUS_ALT: "[a]",
                STATUS_REJECT: "[n]",
            }[st]
            text = item["alt"] if (show_alt[i] and item.get("alt")) else item["after"]
            topic = (item.get("topic_name") or "")[:18]
            topic_s = f"[{topic}]".ljust(20) if topic else " " * 20
            prefix = "> " if is_cursor else "  "
            line = f"{prefix}{mark} {topic_s} {text}"

            attr = curses.A_NORMAL
            if is_cursor:
                attr |= curses.A_BOLD
            if st == STATUS_AFTER:
                attr |= color(1)
            elif st == STATUS_ALT:
                attr |= color(4)
            elif st == STATUS_REJECT:
                attr |= color(2)

            stdscr.addnstr(y, 0, line[: w - 1], w - 1, attr)

        sep_y = 1 + list_h
        stdscr.addnstr(sep_y, 0, "-" * (w - 1), w - 1)

        if cursor < submit_idx:
            item = items[cursor]
            before = item.get("before", "")
            after = item.get("after", "")
            alt = item.get("alt") or "(no alt)"
            stdscr.addnstr(sep_y + 1, 0, f"[before] {before}"[: w - 1], w - 1, color(3))
            stdscr.addnstr(sep_y + 2, 0, f"[after ] {after}"[: w - 1], w - 1)
            stdscr.addnstr(sep_y + 3, 0, f"[alt   ] {alt}"[: w - 1], w - 1)
        else:
            warn = "NOTE: peec treats prompt text as immutable. accepted rewrites = delete old prompt + create new. the old prompt_id and its history will be lost."
            words = warn.split(" ")
            lines, cur = [], ""
            for wd in words:
                if len(cur) + len(wd) + 1 > w - 2:
                    lines.append(cur)
                    cur = wd
                else:
                    cur = (cur + " " + wd) if cur else wd
            if cur:
                lines.append(cur)
            for li, line in enumerate(lines[:3]):
                stdscr.addnstr(sep_y + 1 + li, 0, line, w - 1, color(2))

        foot_y = h - 1
        if foot_y > sep_y + 3:
            accepted = sum(1 for s in statuses if s in (STATUS_AFTER, STATUS_ALT))
            rejected = sum(1 for s in statuses if s == STATUS_REJECT)
            pending = sum(1 for s in statuses if s == STATUS_NONE)
            foot = f" accepted:{accepted}  rejected:{rejected}  pending:{pending}  total:{len(items)} "
            stdscr.addnstr(foot_y, 0, foot[: w - 1].ljust(w - 1), w - 1, curses.A_REVERSE)

        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord("k")):
            cursor = max(0, cursor - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            cursor = min(submit_idx, cursor + 1)
        elif key == curses.KEY_PPAGE:
            cursor = max(0, cursor - list_h)
        elif key == curses.KEY_NPAGE:
            cursor = min(submit_idx, cursor + list_h)
        elif key == curses.KEY_HOME:
            cursor = 0
        elif key == curses.KEY_END:
            cursor = submit_idx
        elif key in (ord("y"), ord("Y")) and cursor < submit_idx:
            statuses[cursor] = STATUS_AFTER
            cursor = min(submit_idx, cursor + 1)
        elif key in (ord("a"), ord("A")) and cursor < submit_idx:
            statuses[cursor] = STATUS_ALT if items[cursor].get("alt") else STATUS_AFTER
            cursor = min(submit_idx, cursor + 1)
        elif key in (ord("n"), ord("N")) and cursor < submit_idx:
            statuses[cursor] = STATUS_REJECT
            cursor = min(submit_idx, cursor + 1)
        elif key == 9 and cursor < submit_idx:
            show_alt[cursor] = not show_alt[cursor]
        elif key in (10, 13, curses.KEY_ENTER) and cursor == submit_idx:
            return [
                {
                    "prompt_id": items[i]["prompt_id"],
                    "topic_id": items[i].get("topic_id"),
                    "tag_ids": items[i].get("tag_ids", []),
                    "before": items[i]["before"],
                    "selected_text": items[i]["alt"] if statuses[i] == STATUS_ALT else items[i]["after"],
                    "selection_mode": statuses[i],
                }
                for i in range(len(items))
                if statuses[i] in (STATUS_AFTER, STATUS_ALT)
            ]
        elif key in (ord("q"), 27):
            return None
        elif key == curses.KEY_RESIZE:
            continue


def fallback(items):
    print("curses unavailable — using numbered fallback.", file=sys.stderr)
    for i, item in enumerate(items):
        topic = item.get("topic_name") or ""
        print(f"[{i+1}] topic:{topic}")
        print(f"    before: {item['before']}")
        print(f"    after : {item['after']}")
        if item.get("alt"):
            print(f"    alt   : {item['alt']}")
    print()
    print("enter comma-separated row numbers to accept (after).")
    print("append 'a' on a row to accept its alt (e.g. 3a,5,7a). blank cancels.")
    raw = sys.stdin.readline().strip()
    if not raw:
        return None
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        use_alt = tok.endswith("a")
        if use_alt:
            tok = tok[:-1]
        try:
            i = int(tok) - 1
        except ValueError:
            continue
        if not (0 <= i < len(items)):
            continue
        item = items[i]
        text = item["alt"] if (use_alt and item.get("alt")) else item["after"]
        out.append(
            {
                "prompt_id": item["prompt_id"],
                "topic_id": item.get("topic_id"),
                "tag_ids": item.get("tag_ids", []),
                "before": item["before"],
                "selected_text": text,
                "selection_mode": "ACCEPT_ALT" if use_alt else "ACCEPT_AFTER",
            }
        )
    return out


def main():
    if len(sys.argv) != 3:
        print("usage: picker.py <input.json> <output.json>", file=sys.stderr)
        sys.exit(2)

    in_path, out_path = sys.argv[1], sys.argv[2]
    with open(in_path) as f:
        payload = json.load(f)
    items = payload.get("items", [])
    if not items:
        print("no items to review.", file=sys.stderr)
        sys.exit(0)

    tty = sys.stdin.isatty() and sys.stdout.isatty()
    selected = None
    if tty:
        try:
            selected = curses.wrapper(run_curses, items)
        except curses.error as e:
            print(f"curses failed: {e} — using fallback.", file=sys.stderr)
            selected = fallback(items)
    else:
        selected = fallback(items)

    if selected is None:
        print("cancelled.", file=sys.stderr)
        sys.exit(1)

    with open(out_path, "w") as f:
        json.dump({"project_id": payload.get("project_id"), "accepted": selected}, f, indent=2)

    print(f"wrote {len(selected)} accepted rewrites to {out_path}")


if __name__ == "__main__":
    main()
