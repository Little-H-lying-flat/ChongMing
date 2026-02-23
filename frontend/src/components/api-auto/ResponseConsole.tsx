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
            <div className="mt-6 border-t border-slate-800 pt-6">
                <div className="flex items-center justify-center p-8 text-slate-400">
                    <Activity className="h-6 w-6 animate-pulse mr-2 text-indigo-500" />
                    <span>执行请求中... (Executing Request...)</span>
                </div>
            </div>
        );
    }

    if (!result) return null;

    return (
        <div className="mt-6 border-t border-slate-800 pt-6 space-y-4">
            <h3 className="text-lg font-medium text-slate-200 mb-4 flex items-center gap-2">
                执行控制台 (Execution Console)
                {result.success ? (
                    <Badge className="bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30">成功 (Success)</Badge>
                ) : (
                    <Badge className="bg-rose-500/20 text-rose-400 hover:bg-rose-500/30">失败 (Failed)</Badge>
                )}
            </h3>

            <div className="grid grid-cols-4 gap-4 mb-4">
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-400">总步骤 (Total Steps)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-slate-200">{result.total_steps}</CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-400">通过 (Passed)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-emerald-400">{result.passed_steps}</CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-xs text-slate-400">失败 (Failed)</CardTitle></CardHeader>
                    <CardContent className="py-3 px-4 text-2xl font-semibold text-rose-400">{result.failed_steps}</CardContent>
                </Card>
            </div>

            {/* Render Step Results */}
            <div className="space-y-4">
                {result.results.map((r: ExecutionStepResult, idx: number) => (
                    <Card key={idx} className="bg-slate-950 border-slate-800">
                        <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                            <div className="flex items-center gap-3">
                                {r.status === 'passed' ? <CheckCircle2 className="h-5 w-5 text-emerald-500" /> : <XCircle className="h-5 w-5 text-rose-500" />}
                                <span className="font-medium text-sm text-slate-200">步骤 (Step) {idx + 1} ({r.step_id})</span>
                                <Badge variant="outline" className={r.status_code >= 200 && r.status_code < 300 ? "text-emerald-400 border-emerald-500/30" : "text-rose-400 border-rose-500/30"}>
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
                                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-md text-sm text-rose-400">
                                    {r.error}
                                </div>
                            )}

                            {/* Extracted Values */}
                            {r.extracted_values && Object.keys(r.extracted_values).length > 0 && (
                                <div>
                                    <h4 className="text-xs font-semibold text-slate-500 uppercase mb-2">提取上下文 (Extracted Context)</h4>
                                    <div className="rounded-md border border-slate-800 bg-slate-900 p-2 overflow-x-auto text-sm">
                                        {Object.entries(r.extracted_values).map(([k, v]) => (
                                            <div key={k} className="flex gap-2">
                                                <span className="text-indigo-400 font-medium">{k}:</span>
                                                <span className="text-slate-300">{JSON.stringify(v)}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* Tabs for Raw Details */}
                            <Tabs defaultValue="response" className="w-full">
                                <TabsList className="bg-slate-900 border-slate-800">
                                    <TabsTrigger value="response" className="text-slate-400 hover:text-slate-200 data-[state=active]:bg-slate-800 data-[state=active]:text-white transition-colors">
                                        <Database className="h-3 w-3 mr-2" />
                                        返回响应 (Response)
                                    </TabsTrigger>
                                    <TabsTrigger value="request" className="text-slate-400 hover:text-slate-200 data-[state=active]:bg-slate-800 data-[state=active]:text-white transition-colors">
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
                                                                ? (function () { try { return JSON.parse(r.response_details.body) } catch (e) { return r.response_details.body } })()
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
                                                        ? (function () { try { return JSON.parse(r.assertion_details.actual_response) } catch (e) { return r.assertion_details.actual_response } })()
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
                                                <Badge variant="outline" className="text-indigo-400 border-indigo-500/30 text-xs">{r.request_details.method}</Badge>
                                                <code className="text-xs text-slate-300 bg-slate-900 px-2 py-1 rounded inline-block break-all">
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
                <Card className="bg-slate-900 border-slate-800">
                    <CardHeader className="py-3 px-4 pb-0"><CardTitle className="text-sm text-slate-400">最终执行上下文 (Final Execution Context)</CardTitle></CardHeader>
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
