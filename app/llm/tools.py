"""Tool (function-calling) schemas exposed to Nebius, and the server-side
dispatcher that executes them. Every tool is scoped to the caller's resolved
``staff_id`` -- the model never receives raw database access."""

from __future__ import annotations

from typing import Any

import psycopg

from app.data import memory, schedules

# OpenAI/Nebius tool schema. Datetimes are ISO-8601 strings (e.g. 2026-06-28T09:00:00).
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_my_schedule",
            "description": "List the caller's own upcoming/active shifts, optionally within a date window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "description": "ISO-8601 start of window (optional)."},
                    "date_to": {"type": "string", "description": "ISO-8601 end of window (optional)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a proposed time window collides with the caller's existing shifts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "ISO-8601 start time."},
                    "end": {"type": "string", "description": "ISO-8601 end time."},
                },
                "required": ["start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_shift",
            "description": "Book a new shift for the caller. Rejected automatically if it overlaps an existing shift.",
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {"type": "string", "description": "ISO-8601 start time."},
                    "end": {"type": "string", "description": "ISO-8601 end time."},
                    "role": {"type": "string", "description": "Role for the shift (optional)."},
                    "location": {"type": "string", "description": "Location/site (optional)."},
                    "notes": {"type": "string", "description": "Free-form notes (optional)."},
                },
                "required": ["start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_shift",
            "description": "Change the time/role/location of one of the caller's existing shifts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shift_id": {"type": "string", "description": "ID of the shift to change."},
                    "new_start": {"type": "string", "description": "New ISO-8601 start (optional)."},
                    "new_end": {"type": "string", "description": "New ISO-8601 end (optional)."},
                    "new_role": {"type": "string", "description": "New role (optional)."},
                    "new_location": {"type": "string", "description": "New location (optional)."},
                },
                "required": ["shift_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_shift",
            "description": "Cancel one of the caller's existing shifts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "shift_id": {"type": "string", "description": "ID of the shift to cancel."},
                },
                "required": ["shift_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a durable preference or fact about the caller (e.g. 'prefers morning shifts').",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "The note to remember."},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Look up the caller's remembered preferences/facts relevant to a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search the caller's memory for."},
                },
                "required": ["query"],
            },
        },
    },
]


async def dispatch(
    name: str,
    args: dict[str, Any],
    conn: psycopg.AsyncConnection,
    staff_id: str,
) -> dict[str, Any]:
    """Execute one tool call against the data layer, scoped to staff_id."""
    if name == "get_my_schedule":
        return await schedules.get_my_schedule(conn, staff_id, args.get("date_from"), args.get("date_to"))
    if name == "check_availability":
        return await schedules.check_availability(conn, staff_id, args["start"], args["end"])
    if name == "set_shift":
        return await schedules.set_shift(
            conn, staff_id, args["start"], args["end"],
            args.get("role"), args.get("location"), args.get("notes"),
        )
    if name == "adjust_shift":
        return await schedules.adjust_shift(
            conn, staff_id, args["shift_id"],
            args.get("new_start"), args.get("new_end"),
            args.get("new_role"), args.get("new_location"),
        )
    if name == "cancel_shift":
        return await schedules.cancel_shift(conn, staff_id, args["shift_id"])
    if name == "remember":
        return await memory.remember(staff_id, args["text"])
    if name == "recall":
        return await memory.recall(staff_id, args["query"])
    return {"ok": False, "error": "unknown_tool", "message": f"Unknown tool: {name}"}
