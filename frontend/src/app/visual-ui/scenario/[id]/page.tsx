"use client"

import React, { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Loader2, CheckCircle2, XCircle, AlertCircle } from "lucide-react";
import { format } from "date-fns";
import { ReactCompareSlider, ReactCompareSliderImage } from 'react-compare-slider';

import { executionsService, ExecutionStatus, Execution } from '@/services/executionsService';
import { OmniParserStatus } from '@/components/OmniParserStatus';

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
    }, [params.id]);

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
        const host = process.env.NEXT_PUBLIC_API_URL
            ? new URL(process.env.NEXT_PUBLIC_API_URL).host
            : '127.0.0.1:8000';

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

    const isRunning = execution?.status === ExecutionStatus.PENDING || execution?.status === ExecutionStatus.RUNNING;

    // Flatten steps for rendering
    const allSteps = execution?.step_results?.map((sr: any) => sr) || [];

    return (
        <div className="flex-1 overflow-y-auto p-6 bg-slate-950">
            <div className="max-w-6xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Button variant="ghost" size="icon" onClick={() => router.push('/visual-ui')} className="text-slate-400 hover:text-slate-100 hover:bg-slate-800">
                            <ArrowLeft className="h-5 w-5" />
                        </Button>
                        <div>
                            <h1 className="text-2xl font-bold text-slate-100">执行 ID (Execution): {executionId}</h1>
                            <div className="flex items-center gap-2 mt-1">
                                <span className={`px-2 py-0.5 text-xs rounded-full font-medium border
                                        ${execution?.status === ExecutionStatus.PASSED ? 'bg-green-100 text-green-700 border-green-200' :
                                        execution?.status === ExecutionStatus.FAILED || execution?.status === ExecutionStatus.ERROR ? 'bg-red-100 text-red-700 border-red-200' :
                                            'bg-blue-100 text-blue-700 border-blue-200 animate-pulse'}`}>
                                    {execution?.status || "加载中 (LOADING)"}
                                </span>
                                {wsConnected && (
                                    <span className="flex items-center gap-1 text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full border border-indigo-100">
                                        <span className="relative flex h-2 w-2">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                                            <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                                        </span>
                                        实时 (Live)
                                    </span>
                                )}
                                <span className="text-xs text-muted-foreground ml-2">
                                    总耗时 (Total Duration): {execution?.duration_ms ? (execution.duration_ms / 1000).toFixed(2) : 0}s
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-12 gap-6">
                    {/* Live Canvas / VRT Viewer */}
                    <div className="col-span-8 space-y-6">
                        <Card className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden">
                            <CardHeader className="py-4 border-b border-slate-800 bg-slate-900">
                                <CardTitle className="text-lg flex justify-between items-center text-indigo-400">
                                    <span>👁️ {isRunning ? "实时执行追踪 (Live Execution Trace)" : "执行结果截图 (Execution Result Screenshots)"}</span>
                                    {isRunning && <OmniParserStatus />}
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-0 bg-black min-h-[500px] flex flex-col items-center justify-center relative overflow-hidden group">
                                {isRunning ? (
                                    liveImage ? (
                                        <>
                                            <img src={liveImage} alt="Live Trace" className="object-contain max-h-[700px] w-full" />
                                            <div className="absolute bottom-4 left-4 right-4 bg-black/70 backdrop-blur-md text-white p-3 rounded-lg border border-white/20 shadow-2xl flex items-center gap-3 transform transition-transform group-hover:translate-y-0 translate-y-2 opacity-90 group-hover:opacity-100">
                                                <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                                                <span className="font-medium truncate">{liveStepDesc}</span>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-white/60 flex flex-col items-center gap-4">
                                            <Loader2 className="h-10 w-10 animate-spin text-indigo-500" />
                                            <p>正在启动无头浏览器与OmniParser识别流... (Starting headless browser and OmniParser recognition flow...)</p>
                                        </div>
                                    )
                                ) : (
                                    // End of run: Show standard screenshot or compare slider 
                                    allSteps.length > 0 && allSteps[allSteps.length - 1].screenshot ? (
                                        <div className="w-full h-full p-4 relative">
                                            {/* Simulated Compare Slider - Normally would fetch base_image from step */}
                                            <div className="text-white/70 absolute top-2 right-4 z-10 text-xs bg-black/50 px-2 py-1 rounded">VRT基准线 (VRT Baseline (Mock))</div>
                                            <ReactCompareSlider
                                                itemOne={<ReactCompareSliderImage src={allSteps[allSteps.length - 1].screenshot} style={{ filter: 'grayscale(30%)' }} alt="基准 (Baseline)" />}
                                                itemTwo={<ReactCompareSliderImage src={allSteps[allSteps.length - 1].screenshot} alt="当前 (Current)" />}
                                                className="rounded-lg shadow-2xl border border-white/10"
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
                    <div className="col-span-4">
                        <Card className="h-[calc(100vh-140px)] flex flex-col bg-slate-900 border-slate-800 shadow-xl">
                            <CardHeader className="py-4 border-b border-slate-800">
                                <CardTitle className="text-base flex justify-between items-center text-slate-200">
                                    执行步骤记录 (Execution Step Log)
                                    <span className="text-xs bg-slate-800 text-slate-300 px-2 py-1 rounded-md font-normal">{allSteps.length} 步 (Steps)</span>
                                </CardTitle>
                            </CardHeader>
                            <CardContent className="p-0 flex-1 overflow-y-auto">
                                <div className="divide-y divide-slate-800/50 relative">
                                    {/* Status Line */}
                                    <div className="absolute left-[31px] top-0 bottom-0 w-px bg-slate-800 -z-10" />

                                    {allSteps.length === 0 && !isRunning && (
                                        <div className="p-8 text-center text-slate-500 text-sm">无可用步骤记录 (No step records available)</div>
                                    )}

                                    {allSteps.map((step: any, idx: number) => (
                                        <div key={idx} className={`p-4 hover:bg-slate-800/50 transition-colors border-b border-slate-800/30 ${!step.success ? 'bg-rose-500/10' : ''}`}>
                                            <div className="flex gap-3">
                                                <div className="mt-0.5 bg-slate-900">
                                                    {step.success ? (
                                                        <CheckCircle2 className="h-5 w-5 text-emerald-500 fill-emerald-500/20" />
                                                    ) : (
                                                        <XCircle className="h-5 w-5 text-rose-500 fill-rose-500/20" />
                                                    )}
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex justify-between items-start mb-1">
                                                        <span className="font-medium text-sm text-slate-200">
                                                            #{idx + 1} {step.description || step.details?.step_name || '未知步骤 (Unknown Step)'}
                                                        </span>
                                                        <span className="text-xs text-slate-400 shrink-0 border border-slate-700 rounded px-1.5 py-0.5 bg-slate-950">
                                                            {step.duration_ms.toFixed(0)} ms
                                                        </span>
                                                    </div>
                                                    <div className="text-xs text-slate-400 mt-1 flex gap-2">
                                                        <span className="font-mono bg-slate-800 text-slate-300 px-1 rounded">{step.details?.action_taken || "Action"}</span>
                                                        <span className="truncate" title={step.details?.target_description}>{step.details?.target_description || ""}</span>
                                                    </div>

                                                    {!step.success && step.error && (
                                                        <div className="mt-2 text-xs text-rose-400 bg-rose-500/10 p-2 rounded border border-rose-500/20 flex items-start gap-1.5">
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
                                        <div className="p-4 bg-indigo-500/10 border-l-2 border-indigo-500">
                                            <div className="flex gap-3 items-center">
                                                <Loader2 className="h-5 w-5 animate-spin text-indigo-500 bg-slate-900 rounded-full" />
                                                <div className="flex-1">
                                                    <div className="font-medium text-sm text-indigo-300">
                                                        #{allSteps.length + 1} {liveStepDesc || "分析中... (Analysis in progress...)"}
                                                    </div>
                                                    <div className="text-xs text-indigo-500/80 mt-1">智能等待 / 执行中... (Smart Wait / Executing...)</div>
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
