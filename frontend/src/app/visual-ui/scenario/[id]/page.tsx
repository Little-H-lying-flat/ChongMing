"use client"

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ArrowLeft, Loader2, CheckCircle2, XCircle, AlertCircle, Eye } from "lucide-react";

import { API_ORIGIN } from '@/services/api';
import { executionsService, ExecutionStatus, Execution } from '@/services/executionsService';
import { VisionStatus } from '@/components/VisionStatus';

interface StepResult {
    step_index?: number;
    success: boolean;
    description?: string;
    details?: { step_name?: string; action_taken?: string; target_description?: string };
    duration_ms: number;
    error?: string;
    screenshot?: string;
}

export default function VisualScenarioPage() {
    const params = useParams();
    const router = useRouter();
    const [executionId, setExecutionId] = useState<string | null>(null);
    const [execution, setExecution] = useState<Execution | null>(null);

    // Live Trace State
    const [liveImage, setLiveImage] = useState<string | null>(null);
    const [liveStepDesc, setLiveStepDesc] = useState<string>("等待引擎接入... (Waiting for engine connection...)");
    const [wsConnected, setWsConnected] = useState(false);

    const wsRef = useRef<WebSocket | null>(null);
    const pollInterval = useRef<NodeJS.Timeout | null>(null);

    const fetchExecutionResult = async (id: string) => {
        try {
            const res = await executionsService.getExecutionResult(id);
            setExecution(res.data);
            if (res.data.status !== ExecutionStatus.PENDING && res.data.status !== ExecutionStatus.RUNNING) {
                if (pollInterval.current) clearInterval(pollInterval.current);
            }
        } catch (err) {
            console.error("Failed to fetch execution:", err);
        }
    };

    const startPolling = (id: string) => {
        if (pollInterval.current) clearInterval(pollInterval.current);
        pollInterval.current = setInterval(() => {
            fetchExecutionResult(id);
        }, 3000);
    };

    const connectWebSocket = (id: string) => {
        // Determine WS URL based on current host config
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = new URL(API_ORIGIN).host;

        const wsUrl = `${protocol}//${host}/api/v1/visual-ui/ws/${id}`;
        const ws = new WebSocket(wsUrl);
        wsRef.current = ws;

        ws.onopen = () => {
            setWsConnected(true);
            console.log("Visual Live Trace Connected");
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.event === 'live_trace') {
                    setLiveImage(data.image_b64);
                    setLiveStepDesc(data.step_description);
                }
            } catch (e) {
                console.error("Failed to parse WS msg", e);
            }
        };

        ws.onclose = () => {
            setWsConnected(false);
        };
    };

    useEffect(() => {
        if (params.id && typeof params.id === 'string') {
            setExecutionId(params.id);
            fetchExecutionResult(params.id);
            connectWebSocket(params.id);
            startPolling(params.id);
        }
        return () => {
            if (wsRef.current) wsRef.current.close();
            if (pollInterval.current) clearInterval(pollInterval.current);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [params.id]);

    const isRunning = execution?.status === ExecutionStatus.PENDING || execution?.status === ExecutionStatus.RUNNING;

    const allSteps = (execution?.cases?.flatMap((testCase) => testCase.steps || []) as StepResult[] | undefined)
        || ((execution?.step_results || []) as unknown as StepResult[]);
    const finalScreenshot = allSteps[allSteps.length - 1]?.screenshot;
    const totalDurationSeconds = execution?.duration_seconds ?? (execution?.duration_ms ? execution.duration_ms / 1000 : 0);
    const passedSteps = allSteps.filter((step) => step.success).length;
    const failedSteps = allSteps.filter((step) => !step.success).length;
    const progressValue = allSteps.length > 0 ? Math.round((passedSteps / allSteps.length) * 100) : (isRunning ? 15 : 0);

    const statusBadgeClass = (status?: ExecutionStatus) => {
        if (status === ExecutionStatus.PASSED) return 'border-emerald-200 bg-emerald-50 text-emerald-700';
        if (status === ExecutionStatus.FAILED || status === ExecutionStatus.ERROR) return 'border-rose-200 bg-rose-50 text-rose-700';
        if (status === ExecutionStatus.CANCELLED) return 'border-slate-200 bg-slate-100 text-slate-600';
        return 'border-blue-200 bg-blue-50 text-blue-700';
    };

    return (
        <div className="flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top_left,rgba(14,165,233,0.16),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(245,158,11,0.12),transparent_28%),linear-gradient(135deg,#f8fafc,#eef6ff_52%,#fff7ed)] p-6 text-slate-900">
            <div className="max-w-6xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" aria-label="返回 Visual UI 页面 (Back to Visual UI)" onClick={() => router.push('/visual-ui')} className="text-slate-500 hover:bg-sky-50 hover:text-sky-700">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-950">执行 ID (Execution): {executionId}</h1>
                            <div className="flex flex-wrap items-center gap-2 mt-1">
                                <Badge variant="outline" className={statusBadgeClass(execution?.status)}>
                                    {execution?.status || "加载中 (LOADING)"}
                                </Badge>
                                {wsConnected && (
                                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-sky-500"></span>
                                        </span>
                                        实时 (Live)
                                    </Badge>
                                )}
                                <span className="text-xs text-slate-500">
                                    总耗时 (Total Duration): {totalDurationSeconds.toFixed(2)}s
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <Card className="rounded-2xl border-white/70 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.45)] backdrop-blur-xl">
                    <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4">
                        <div>
                            <div className="text-xs text-slate-500">步骤总数 (Total Steps)</div>
                            <div className="text-lg font-semibold text-slate-950">{allSteps.length}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">通过 (Passed)</div>
                            <div className="text-lg font-semibold text-emerald-700">{passedSteps}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">失败 (Failed)</div>
                            <div className="text-lg font-semibold text-rose-700">{failedSteps}</div>
                        </div>
                        <div>
                            <div className="text-xs text-slate-500">进度 (Progress)</div>
                            <div className="mt-2 flex items-center gap-2">
                                <Progress value={progressValue} className="h-2 bg-sky-100" />
                                <span className="text-xs text-slate-600">{progressValue}%</span>
                            </div>
                        </div>
                    </CardContent>
                </Card>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                    {/* Live Canvas / Screenshot Viewer */}
                    <div className="col-span-12 lg:col-span-8 space-y-6">
                        <Card className="overflow-hidden rounded-2xl border-white/70 bg-white/80 shadow-xl backdrop-blur-xl">
                            <CardHeader className="border-b border-sky-100 bg-gradient-to-r from-sky-50 to-white py-4">
                                <CardTitle className="text-lg flex justify-between items-center text-sky-700">
                                    <span className="flex items-center gap-2">
                                        <Eye className="h-5 w-5" aria-hidden="true" />
                                        {isRunning ? "实时执行追踪 (Live Execution Trace)" : "执行结果截图 (Execution Result Screenshots)"}
                                    </span>
                                    {isRunning && <VisionStatus />}
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-0 bg-black min-h-[500px] flex flex-col items-center justify-center relative overflow-hidden group">
                                {isRunning ? (
                                    liveImage ? (
                                        <>
                                            {/* eslint-disable-next-line @next/next/no-img-element */}
                                            <img src={liveImage} alt="Live Trace" className="object-contain max-h-[700px] w-full" />
                                            <div className="absolute bottom-4 left-4 right-4 bg-black/70 backdrop-blur-md text-white p-3 rounded-lg border border-white/20 shadow-2xl flex items-center gap-3 transform transition-transform group-hover:translate-y-0 translate-y-2 opacity-90 group-hover:opacity-100">
                                                <Loader2 className="h-5 w-5 animate-spin text-sky-300" />
                                                <span className="font-medium truncate">{liveStepDesc}</span>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-white/60 flex flex-col items-center gap-4">
                                            <Loader2 className="h-10 w-10 animate-spin text-sky-400" />
                                            <p>正在启动浏览器与视觉执行器... (Starting browser and vision executor...)</p>
                                        </div>
                                    )
                                ) : (
                                    finalScreenshot ? (
                                        <div className="w-full h-full p-4 relative flex flex-col gap-3">
                                            <div className="text-white/70 text-xs bg-black/50 px-3 py-2 rounded border border-white/10 self-start">
                                                当前展示真实执行截图；未配置基准图时不进行视觉回归对比。 (Showing the real execution screenshot. No VRT comparison is shown without a real baseline.)
                                            </div>
                                            {/* eslint-disable-next-line @next/next/no-img-element */}
                                            <img
                                                src={finalScreenshot}
                                                alt="最终执行截图 (Final execution screenshot)"
                                                className="w-full max-h-[700px] object-contain rounded-lg shadow-2xl border border-white/10"
                                            />
                                        </div>
                                    ) : (
                                        <div className="text-white/40">无可用的执行截图 (No execution screenshots available)</div>
                                    )
                                )}
                            </CardContent>
                        </Card>
                    </div>

                    {/* Step Execution Log */}
                    <div className="col-span-12 lg:col-span-4">
                        <Card className="h-[calc(100vh-140px)] flex flex-col rounded-2xl border-white/70 bg-white/80 shadow-xl backdrop-blur-xl">
                            <CardHeader className="border-b border-sky-100 py-4">
                                <CardTitle className="text-base flex justify-between items-center text-slate-900">
                                    执行步骤记录 (Execution Step Log)
                                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">{allSteps.length} 步 (Steps)</Badge>
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-0 flex-1 overflow-y-auto">
                                <div className="divide-y divide-slate-800/50 relative">
                                    {/* Status Line */}
                                    <div className="absolute left-[31px] top-0 bottom-0 w-px bg-sky-100 -z-10" />

                                    {allSteps.length === 0 && !isRunning && (
                                        <div className="p-8 text-center text-slate-500 text-sm">无可用步骤记录 (No step records available)</div>
                                    )}

                                    {allSteps.map((step, idx) => (
                                        <div key={idx} className={`border-b border-slate-100 p-4 transition-colors hover:bg-sky-50/70 ${!step.success ? 'bg-rose-50/70' : ''}`}>
                                            <div className="flex gap-3">
                                                <div className="mt-0.5 rounded-full bg-white">
                                                    {step.success ? (
                                                        <CheckCircle2 className="h-5 w-5 text-emerald-500 fill-emerald-500/20" />
                                                    ) : (
                                                        <XCircle className="h-5 w-5 text-rose-500 fill-rose-500/20" />
                                                    )}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex justify-between items-start mb-1">
                                                        <span className="font-medium text-sm text-slate-800">
                                                            #{(step.step_index ?? idx) + 1} {step.description || step.details?.step_name || '未知步骤 (Unknown Step)'}
                                                        </span>
                                                        <Badge variant="outline" className="border-slate-200 bg-white text-slate-500">
                                                            {step.duration_ms.toFixed(0)} ms
                                                        </Badge>
                                                    </div>
                                                    <div className="text-xs text-slate-500 mt-1 flex gap-2">
                                                        <Badge variant="outline" className="border-blue-200 bg-blue-50 text-blue-700 uppercase">{step.details?.action_taken || "Action"}</Badge>
                                                        <span className="truncate" title={step.details?.target_description}>{step.details?.target_description || ""}</span>
                                                    </div>

                                                    {!step.success && step.error && (
                                                        <div className="mt-2 flex items-start gap-1.5 rounded border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                                                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                                                            <span className="break-all">{step.error}</span>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        </div>
                                    ))}

                                    {/* Fake Pending Step Entry for Live Feel */}
                                    {isRunning && (
                                        <div className="border-l-2 border-sky-500 bg-sky-50 p-4">
                                            <div className="flex gap-3 items-center">
                                                <Loader2 className="h-5 w-5 animate-spin rounded-full bg-white text-sky-500" />
                                                <div className="flex-1">
                                                    <div className="font-medium text-sm text-sky-700">
                                                        #{allSteps.length + 1} {liveStepDesc || "分析中... (Analysis in progress...)"}
                                                    </div>
                                                    <div className="text-xs text-sky-600 mt-1">智能等待 / 执行中... (Smart Wait / Executing...)</div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </div>
    );
}
