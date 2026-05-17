import React from "react";
import JsonView from '@uiw/react-json-view';
import { vscodeTheme } from '@uiw/react-json-view/vscode';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChainExecutionResult, ExecutionStepResult } from "@/services/apiAutoService";
import { Activity, Clock, CheckCircle2, XCircle, Send, Database } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface ResponseConsoleProps {
    result: ChainExecutionResult | null;
    isLoading: boolean;
}

export function ResponseConsole({ result, isLoading }: ResponseConsoleProps) {
    if (isLoading) {
        return (
            <div className="mt-6 border-t border-sky-100 pt-6">
                <div className="flex items-center justify-center p-8 text-slate-600">
                    <Activity className="h-6 w-6 animate-pulse mr-2 text-sky-500" />
                    <span>执行请求中... (Executing Request...)</span>
                </div>
            </div>
        );
    }

    if (!result) return null;

    return (
        <div className="mt-6 border-t border-sky-100 pt-6 space-y-4">
            <h3 className="text-lg font-medium text-slate-900 mb-4 flex items-center gap-2">
                执行控制台 (Execution Console)
                {result.success ? (
                    <Badge className="border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100">成功 (Success)</Badge>
                ) : (
                    <Badge className="border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100">失败 (Failed)</Badge>
                )}
            </h3>

            <div className="grid grid-cols-4 gap-4 mb-4">
                <Card className="border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-500">总步骤 (Total Steps)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-slate-950">{result.total_steps}</CardContent>
                </Card>
                <Card className="border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-500">通过 (Passed)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-emerald-400">{result.passed_steps}</CardContent>
                </Card>
                <Card className="border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-500">失败 (Failed)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-rose-400">{result.failed_steps}</CardContent>
                </Card>
            </div>

            {/* Render Step Results */}
            <div className="space-y-4">
                {result.results.map((r: ExecutionStepResult, idx: number) => (
                    <Card key={idx} className="overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                        <div className="p-3 border-b border-sky-100 flex items-center justify-between bg-sky-50/60">
                            <div className="flex items-center gap-3">
                                {r.status === 'passed' ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : <XCircle className="h-5 w-5 text-rose-500" />}
                                <span className="font-medium text-sm text-slate-900">步骤 (Step) {idx + 1} ({r.step_id})</span>
                                <Badge variant="outline" className={r.status_code >= 200 && r.status_code < 300 ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-rose-50 text-rose-700 border-rose-200"}>
                                    {r.status_code || 'Err'}
                                </Badge>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-slate-500">
                                <Clock className="h-3 w-3" />
                                {r.duration_ms} ms
                            </div>
                        </div>
                        <div className="p-4 space-y-4">
                            {r.error && (
                                <div className="p-3 bg-rose-50 border border-rose-200 rounded-md text-sm text-rose-700">
                                    {r.error}
                                </div>
                            )}

                            {/* Extracted Values */}
                            {r.extracted_values && Object.keys(r.extracted_values).length > 0 && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">提取上下文 (Extracted Context)</h4>
                                    <div className="rounded-xl border border-sky-100 bg-sky-50/70 p-3 overflow-x-auto text-sm">
                                        {Object.entries(r.extracted_values).map(([k, v]) => (
                                            <div key={k} className="flex gap-2">
                                                <span className="text-violet-700 font-medium">{k}:</span>
                                                <span className="text-slate-700">{JSON.stringify(v)}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Tabs for Raw Details */}
                            <Tabs defaultValue="response" className="w-full">
                                <TabsList className="border border-sky-100 bg-sky-50/70">
                                    <TabsTrigger value="response" className="text-slate-600 hover:text-sky-800 data-[state=active]:bg-white data-[state=active]:text-sky-700 data-[state=active]:shadow-sm transition-colors">
                                        <Database className="h-3 w-3 mr-2" />
                                        返回响应 (Response)
                                    </TabsTrigger>
                                    <TabsTrigger value="request" className="text-slate-600 hover:text-violet-800 data-[state=active]:bg-white data-[state=active]:text-violet-700 data-[state=active]:shadow-sm transition-colors">
                                        <Send className="h-3 w-3 mr-2" />
                                        发送请求 (Request)
                                    </TabsTrigger>
                                </TabsList>

                                <TabsContent value="response" className="space-y-4 outline-none">
                                    {r.response_details ? (
                                        <>
                                            {r.response_details.headers && Object.keys(r.response_details.headers).length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">响应头 (Response Headers)</h4>
                                                    <div className="rounded-md border border-slate-800 bg-[#1e1e1e] p-2 overflow-x-auto text-sm">
                                                        <JsonView value={r.response_details.headers} style={vscodeTheme} shortenTextAfterLength={99999} collapsed={false} />
                                                    </div>
                                                </div>
                                            )}
                                            {r.response_details.body !== undefined && r.response_details.body !== null ? (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">响应体 (Response Body)</h4>
                                                    <div className="rounded-md border border-slate-800 overflow-hidden bg-[#1e1e1e] p-2 max-h-96 overflow-y-auto">
                                                        <JsonView
                                                            value={typeof r.response_details.body === 'string'
                                                                ? (function () { try { return JSON.parse(r.response_details.body as string) } catch (_e) { return r.response_details.body } })()
                                                                : r.response_details.body}
                                                            style={vscodeTheme}
                                                            shortenTextAfterLength={99999}
                                                            collapsed={false}
                                                            displayDataTypes={false}
                                                        />
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="text-sm text-slate-500 p-4 text-center">空响应体 (Empty Response Body)</div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="text-sm text-slate-500 p-4 text-center text-rose-500">无法获取最新响应数据 (Cannot fetch latest response data)</div>
                                    )}
                                    {/* Fallback to old assertion_details.actual_response if response_details is not present from backend yet */}
                                    {!r.response_details && r.assertion_details && r.assertion_details.actual_response !== undefined && (
                                        <div>
                                            <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">响应体 (Response Body)</h4>
                                            <div className="rounded-md border border-slate-800 overflow-hidden bg-[#1e1e1e] p-2 max-h-96 overflow-y-auto">
                                                <JsonView
                                                    value={typeof r.assertion_details.actual_response === 'string'
                                                        ? (function () { try { return JSON.parse(r.assertion_details.actual_response as string) } catch (_e) { return r.assertion_details.actual_response } })()
                                                        : r.assertion_details.actual_response}
                                                    style={vscodeTheme}
                                                    shortenTextAfterLength={99999}
                                                    collapsed={false}
                                                    displayDataTypes={false}
                                                />
                                            </div>
                                        </div>
                                    )}
                                </TabsContent>

                                <TabsContent value="request" className="space-y-4 outline-none">
                                    {r.request_details ? (
                                        <>
                                            <div className="flex items-center gap-2 mb-2">
                                                <Badge variant="outline" className="bg-violet-50 text-violet-700 border-violet-200 text-xs">{r.request_details.method}</Badge>
                                                <code className="text-xs text-slate-700 bg-sky-50 border border-sky-100 px-2 py-1 rounded inline-block break-all">
                                                    {r.request_details.url}
                                                </code>
                                            </div>
                                            {r.request_details.headers && Object.keys(r.request_details.headers).length > 0 && (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">请求头 (Request Headers)</h4>
                                                    <div className="rounded-md border border-slate-800 bg-[#1e1e1e] p-2 overflow-x-auto text-sm">
                                                        <JsonView value={r.request_details.headers} style={vscodeTheme} shortenTextAfterLength={99999} collapsed={false} />
                                                    </div>
                                                </div>
                                            )}
                                            {r.request_details.body !== undefined && r.request_details.body !== null && (
                                                <div>
                                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">请求体 (Request Body)</h4>
                                                    <div className="rounded-md border border-slate-800 overflow-hidden bg-[#1e1e1e] p-2 max-h-96 overflow-y-auto">
                                                        <JsonView value={r.request_details.body} style={vscodeTheme} shortenTextAfterLength={99999} collapsed={false} displayDataTypes={false} />
                                                    </div>
                                                </div>
                                            )}
                                        </>
                                    ) : (
                                        <div className="text-sm text-slate-500 p-4 text-center">暂无请求体数据 (No request data available)</div>
                                    )}
                                </TabsContent>
                            </Tabs>
                        </div>
                    </Card>
                ))}
            </div>

            {/* Final Context */}
            {result.final_context && Object.keys(result.final_context).length > 0 && (
                <Card className="border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-sm text-slate-600">最终执行上下文 (Final Execution Context)</CardTitle></CardHeader>
                    <CardContent className="p-4">
                        <div className="rounded-md border border-slate-800 overflow-hidden bg-[#1e1e1e] p-2">
                            <JsonView value={result.final_context} style={vscodeTheme} shortenTextAfterLength={99999} collapsed={false} displayDataTypes={false} />
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
