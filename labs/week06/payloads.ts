import type { z } from "zod";
import { ToolCall, ToolResult, ToolSpec } from "./zod-tools.js";

export interface Case {
    readonly id: number;
    readonly label: string;
    readonly schema: z.ZodType;
    readonly json: string;
}

export const CASES: readonly Case[] = [
    { id: 1, label: "ToolCall with no name", schema: ToolCall,
    json: '{"id": "123", "arguments": {"pod": "api-7f9", "lines": 100}}' },
    { id: 2, label: "arguments is a string", schema: ToolCall,
    json: '{"id": "123", "name": "test_tool", "arguments": "api-7f9"}' },
    { id: 3, label: "extra arguments", schema: ToolCall,
    json: '{"id": "123", "name": "test_tool", "arguments": {"pod": "api-7f9", "lines": 100}, "extra_field": "extra_value"}' },
    { id: 4, label: "unknown kind value", schema: ToolResult,
    json: '{"call_id": "123", "outcome": {"kind": "done", "content": "This should not be allowed"}}' },
    { id: 5, label: "error kind", schema: ToolResult,
    json: '{"call_id": "123", "outcome": {"kind": "error", "content": "This should not be allowed"}}' },
    { id: 6, label: "Name validation", schema: ToolSpec,
    json: '{"name": 43, "description": "A tool without a name", "input_schema": {"param": "value"}}' },
]