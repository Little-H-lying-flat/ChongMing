import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Send, Play, AlignLeft, Variable, CheckSquare } from "lucide-react";
import { KeyValueEditor } from "./KeyValueEditor";
import { ApiStep } from "@/services/apiAutoService";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

interface RequestBuilderProps {
    step: ApiStep;
    onChange: (step: ApiStep) => void;
    onRun: () => void;
    isExecuting: boolean;
}

const METHOD_COLORS = {
    GET: "text-blue-400 font-bold",
    POST: "text-emerald-400 font-bold",
    PUT: "text-amber-400 font-bold",
    DELETE: "text-rose-400 font-bold",
    PATCH: "text-purple-400 font-bold",
} as Record<string, string>;

export function RequestBuilder({ step, onChange, onRun, isExecuting }: RequestBuilderProps) {
    const [activeTab, setActiveTab] = useState("params");

    const updateRequest = (field: keyof ApiStep['request'], value: any) => {
        onChange({ ...step, request: { ...(step.request || {}), [field]: value } });
    };

    // Convert Record<string, string> back and forth from KeyValuePair[]
    const recordToPairs = React.useCallback((record: Record<string, string> = {}) => {
        return Object.entries(record).map(([key, value]) => ({ key, value }));
    }, []);

    const pairsToRecord = (pairs: { key: string; value: string }[]) => {
        const record: Record<string, string> = {};
        pairs.forEach(p => {
            if (p.key.trim()) record[p.key.trim()] = p.value;
        });
        return record;
    };

    const [queryParams, setQueryParams] = useState(recordToPairs(step.request?.query_params || {}));
    const [headers, setHeaders] = useState(recordToPairs(step.request?.headers || {}));
    const [extraction, setExtraction] = useState(recordToPairs(step.extraction || {}));
    const [jsonAssertions, setJsonAssertions] = useState(recordToPairs(step.assertion?.json_assertions || {}));

    // Reset local pairs state when active step changes
    React.useEffect(() => {
        setQueryParams(recordToPairs(step.request?.query_params || {}));
        setHeaders(recordToPairs(step.request?.headers || {}));
        setExtraction(recordToPairs(step.extraction || {}));
        setJsonAssertions(recordToPairs(step.assertion?.json_assertions || {}));
    }, [step.id, recordToPairs, step.request, step.extraction, step.assertion]);

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-2">
                <Select
                    value={step.request?.method || "GET"}
                    onValueChange={(val: any) => updateRequest("method", val)}
                >
                    <SelectTrigger className={`w-32 bg-slate-900 border-slate-700 ${METHOD_COLORS[step.request?.method || "GET"] || ''}`}>
                        <SelectValue placeholder="Method" />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-900 border-slate-700">
                        {Object.keys(METHOD_COLORS).map(m => (
                            <SelectItem key={m} value={m} className={METHOD_COLORS[m]}>{m}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <div className="flex-1 relative">
                    <Input
                        value={step.request?.url || ""}
                        onChange={(e) => updateRequest("url", e.target.value)}
                        placeholder="https://api.example.com/v1/users/${user_id}"
                        className="w-full bg-slate-900 border-slate-700 text-slate-100 font-mono text-sm h-10 pr-4"
                    />
                </div>

                <Button
                    onClick={onRun}
                    disabled={isExecuting}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white min-w-24 h-10"
                >
                    {isExecuting ? (
                        <span className="flex items-center"><span className="animate-spin mr-2">◷</span> 发送中... (Sending...)</span>
                    ) : (
                        <span className="flex items-center"><Send className="h-4 w-4 mr-2" /> 发送 (Send)</span>
                    )}
                </Button>
            </div>

            <Card className="bg-slate-900 border-slate-800 rounded-md overflow-hidden">
                <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                    <div className="border-b border-slate-800 bg-slate-950/50 px-2 py-1">
                        <TabsList className="bg-transparent h-9 p-0 space-x-2">
                            <TabsTrigger value="params" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-400">参数 (Params)</TabsTrigger>
                            <TabsTrigger value="headers" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-400">请求头 (Headers)</TabsTrigger>
                            <TabsTrigger value="body" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-slate-400">请求体 (Body)</TabsTrigger>
                            <TabsTrigger value="extraction" className="data-[state=active]:bg-slate-800 data-[state=active]:text-slate-100 text-indigo-400">
                                <Variable className="h-3 w-3 mr-1" /> 提取 (Extraction)
                            </TabsTrigger>
                            <TabsTrigger value="assertion" className="data-[state=active]:bg-slate-800 data-[state=active]:text-emerald-400 text-emerald-600/70">
                                <CheckSquare className="h-3 w-3 mr-1" /> 断言 (Assertion)
                            </TabsTrigger>
                        </TabsList>
                    </div>
                    <CardContent className="p-0 min-h-[300px]">
                        <TabsContent value="params" className="m-0 p-4">
                            <KeyValueEditor
                                pairs={queryParams}
                                onChange={(p) => {
                                    setQueryParams(p);
                                    updateRequest("query_params", pairsToRecord(p));
                                }}
                                placeholderKey="查询参数 (Query Param)"
                            />
                        </TabsContent>
                        <TabsContent value="headers" className="m-0 p-4">
                            <KeyValueEditor
                                pairs={headers}
                                onChange={(p) => {
                                    setHeaders(p);
                                    updateRequest("headers", pairsToRecord(p));
                                }}
                                placeholderKey="请求头名称 (Header Name)"
                                placeholderValue="请求头值 (Header Value)"
                            />
                        </TabsContent>
                        <TabsContent value="body" className="m-0 p-0 h-full flex flex-col">
                            <div className="p-4 bg-slate-900 border-b border-slate-800 text-xs text-slate-400 flex items-center gap-2">
                                <AlignLeft className="h-4 w-4" /> JSON 载荷 (JSON Payload)
                            </div>
                            <Textarea
                                value={typeof step.request.body === 'string' ? step.request.body : JSON.stringify(step.request.body, null, 2)}
                                onChange={(e) => {
                                    try {
                                        updateRequest("body", JSON.parse(e.target.value));
                                    } catch {
                                        updateRequest("body", e.target.value); // keep as string if not valid JSON
                                    }
                                }}
                                className="flex-1 min-h-[250px] bg-[#1e1e1e] border-0 rounded-none text-slate-300 font-mono text-sm p-4 focus-visible:ring-0 resize-none"
                                placeholder={'{\n  "key": "value"\n}'}
                            />
                        </TabsContent>
                        <TabsContent value="extraction" className="m-0 p-4">
                            <div className="mb-4 text-sm text-slate-400">
                                提取响应JSON中的字段作为全局变量 (Extract response JSON fields as global variables). Example: <code className="text-indigo-400 bg-indigo-400/10 px-1 rounded">token</code> &larr; <code className="text-amber-400 bg-amber-400/10 px-1 rounded">$.data.access_token</code>)
                            </div>
                            <KeyValueEditor
                                pairs={extraction}
                                onChange={(p) => {
                                    setExtraction(p);
                                    onChange({ ...step, extraction: pairsToRecord(p) });
                                }}
                                placeholderKey="变量名 e.g. user_id (Variable Name)"
                                placeholderValue="提取路径 e.g. $.data.id (JSONPath)"
                            />
                        </TabsContent>
                        <TabsContent value="assertion" className="m-0 p-4 space-y-4">
                            <div className="flex items-center gap-4">
                                <label className="text-sm font-medium text-slate-300 w-32">预期状态码 (Expected Status):</label>
                                <Input
                                    type="number"
                                    value={step.assertion?.status_code || ""}
                                    onChange={e => onChange({ ...step, assertion: { ...step.assertion, json_assertions: step.assertion?.json_assertions || {}, status_code: parseInt(e.target.value) || undefined } })}
                                    placeholder="200"
                                    className="w-32 bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500"
                                />
                            </div>

                            <div className="flex items-start gap-4">
                                <label className="text-sm font-medium text-slate-300 w-32 pt-2">JSON匹配 (JSON Match):</label>
                                <div className="flex-1">
                                    <KeyValueEditor
                                        pairs={jsonAssertions}
                                        onChange={(p) => {
                                            setJsonAssertions(p);
                                            onChange({ ...step, assertion: { ...step.assertion, json_assertions: pairsToRecord(p), status_code: step.assertion?.status_code } });
                                        }}
                                        placeholderKey="匹配路径 e.g. $.code (JSONPath)"
                                        placeholderValue="预期值 e.g. 0 (Expected Value)"
                                    />
                                </div>
                            </div>

                            <div className="flex items-center gap-4">
                                <label className="text-sm font-medium text-slate-300 w-32">包含文本 (Contains Text):</label>
                                <Input
                                    value={step.assertion?.contains || ""}
                                    onChange={e => onChange({ ...step, assertion: { ...step.assertion, json_assertions: step.assertion?.json_assertions || {}, contains: e.target.value } })}
                                    placeholder="Success"
                                    className="flex-1 bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500"
                                />
                            </div>
                        </TabsContent>
                    </CardContent>
                </Tabs>
            </Card>
        </div>
    );
}
