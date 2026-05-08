"use client";

import { X, CheckCircle, XCircle, Clock, Terminal, ChevronRight, Activity, ArrowRight, Database } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { toast } from "sonner";
import { useRef, useState, useEffect } from "react";
import { cn } from "@/lib/utils";

const scrollbarStyles = `
  .geek-scrollbar::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  .geek-scrollbar::-webkit-scrollbar-track {
    background: transparent;
  }
  .geek-scrollbar::-webkit-scrollbar-thumb {
    background: #334155;
    border-radius: 3px;
  }
  .geek-scrollbar::-webkit-scrollbar-thumb:hover {
    background: #475569;
  }
`;

interface StepDetail {
    step_name: string;
    step_type?: "API" | "UI";
    // API fields
    request?: {
        url: string;
        method: string;
        headers: Record<string, unknown>;
        body: unknown;
    };
    response?: {
        status: number;
        headers: Record<string, unknown>;
        body: unknown;
    };
    extracted?: Record<string, unknown>;
    assertions_failed?: string[];
    // UI fields
    action_taken?: string;
    target_description?: string;
    screenshot_before?: string;
    screenshot_after?: string;
    page_url?: string;
    page_title?: string;
    strategy?: string;
    // Warnings
    warnings?: {
        type: string;
        message: string;
        details?: unknown;
    }[];
}

interface StepResult {
    step_index: number;
    success: boolean;
    duration_ms: number;
    error?: string;
    description?: string; // Added description
    details?: StepDetail;
}

interface CaseResult {
    tc_id: string;
    status: string;
    duration_ms: number;
    steps: StepResult[];

    variable_trace?: {
        var_name: string;
        value: unknown;
        source_step_index: number;
        source_step_name: string;
    }[];
    error?: string;
}

interface ExecutionDetail {
    execution_id: string;
    status: string;
    cases: CaseResult[];
}

interface ExecutionDrawerProps {
    executionId: string | null;
    open: boolean;
    onClose: () => void;
}

export function ExecutionDrawer({ executionId, open, onClose }: ExecutionDrawerProps) {
    const [data, setData] = useState<ExecutionDetail | null>(null);
    const [loading, setLoading] = useState(false);
    const toastedSteps = useRef<Set<string>>(new Set());
    const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Toast Trigger for Vision Failures
    useEffect(() => {
        if (!data) return;
        data.cases.forEach(tc => {
            tc.steps.forEach(step => {
                const stepId = `${tc.tc_id}-${step.step_index}`;
                const details = step.details as StepDetail;
                if (details?.warnings?.some(w => w.type === 'VISION_ELEMENT_NOT_FOUND') && !toastedSteps.current.has(stepId)) {
                    toast.warning("视觉感知未命中 (Vision Element Not Found)", {
                        description: `当前页面截图中未找到目标元素 (Target element not found in screenshot) [${details.target_description || 'Unknown'}], aborted or degraded. `,
                        duration: 5000,
                        className: "bg-amber-950 border-amber-500 text-amber-200",
                    });
                    toastedSteps.current.add(stepId);
                }
            });
        });
    }, [data]);

    // Auto-open first failed step or first step
    const [openStepIndices, setOpenStepIndices] = useState<string[]>([]);

    useEffect(() => {
        const clearPolling = () => {
            if (pollTimerRef.current) {
                clearInterval(pollTimerRef.current);
                pollTimerRef.current = null;
            }
        };

        const loadExecution = async () => {
            if (!executionId) return;
            try {
                const res = await fetch(`/api/v1/executions/${executionId}/steps`);
                if (!res.ok) {
                    throw new Error(`Failed to fetch execution detail: ${res.status}`);
                }
                const payload = await res.json();
                setData(payload);

                const status = String(payload?.status || "").toLowerCase();
                if (["passed", "failed", "error", "cancelled"].includes(status)) {
                    clearPolling();
                }
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };

        if (open && executionId) {
            setLoading(true);
            void loadExecution();
            clearPolling();
            pollTimerRef.current = setInterval(() => {
                void loadExecution();
            }, 2000);
        } else {
            clearPolling();
            setData(null);
            setOpenStepIndices([]);
        }

        return () => {
            clearPolling();
        };
    }, [open, executionId]);

    const toggleStep = (id: string) => {
        setOpenStepIndices(prev =>
            prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
        );
    };

    const StatusIcon = ({ status }: { status: string }) => {
        if (status === "passed") return <CheckCircle className="w-5 h-5 text-green-500" />;
        if (status === "failed") return <XCircle className="w-5 h-5 text-red-500" />;
        return <Activity className="w-5 h-5 text-slate-400" />;
    };

    const MethodBadge = ({ method }: { method?: string }) => {
        if (!method) return null;
        const colors: Record<string, string> = {
            GET: "bg-blue-500/20 text-blue-400 border-blue-500/50",
            POST: "bg-green-500/20 text-green-400 border-green-500/50",
            PUT: "bg-orange-500/20 text-orange-400 border-orange-500/50",
            DELETE: "bg-red-500/20 text-red-400 border-red-500/50",
        };
        return <Badge variant="outline" className={cn("text-[10px] font-mono h-5", colors[method] || "text-slate-400")}>{method}</Badge>;
    };

    const ActionBadge = ({ action }: { action?: string }) => {
        if (!action) return null;
        const colors: Record<string, string> = {
            click: "bg-purple-500/20 text-purple-400 border-purple-500/50",
            type: "bg-cyan-500/20 text-cyan-400 border-cyan-500/50",
            navigate: "bg-yellow-500/20 text-yellow-400 border-yellow-500/50",
            scroll: "bg-blue-500/20 text-blue-400 border-blue-500/50",
            done: "bg-green-500/20 text-green-400 border-green-500/50",
        };
        return <Badge variant="outline" className={cn("text-[10px] font-mono h-5 uppercase", colors[action] || "text-slate-400")}>{action}</Badge>;
    };

    const normalizedExecutionStatus = (data?.status || "").toLowerCase();
    const hasCaseResults = Boolean(data?.cases?.some((tc) => tc.steps?.length > 0));
    const isActiveExecution = normalizedExecutionStatus === "pending" || normalizedExecutionStatus === "running";
    const isFailedExecution = normalizedExecutionStatus === "failed" || normalizedExecutionStatus === "error" || normalizedExecutionStatus === "cancelled";

    const JsonViewer = ({ data }: { data: unknown }) => {
        if (!data) return <div className="text-slate-500 text-xs italic">No Content</div>;
        const jsonStr = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
        return (
            <div className="bg-[#0D1117] p-3 rounded-md border border-slate-800 overflow-x-auto">
                <pre className="text-[11px] font-mono text-blue-300 leading-relaxed">
                    {jsonStr}
                </pre>
            </div>
        );
    };

    if (!open) return null;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black/60 z-40 backdrop-blur-[2px] transition-opacity"
                onClick={onClose}
            />

            {/* Drawer Panel */}
            <div className="fixed inset-y-0 right-0 w-[800px] bg-slate-950 border-l border-slate-800 shadow-2xl z-50 transform transition-transform duration-300 ease-in-out flex flex-col">

                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-900/80 backdrop-blur">
                    <div>
                        <h3 className="text-lg font-mono font-bold text-slate-100 flex items-center gap-3">
                            <Terminal className="w-5 h-5 text-purple-400" />
                            {executionId}
                        </h3>
                        <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
                            完整执行检查器 (Full Execution Inspector)
                            {data?.status && (
                                <Badge variant="outline" className="text-[10px] h-5 text-white border-slate-700 bg-slate-800/50">{data.status.toUpperCase()}</Badge>
                            )}
                        </p>
                    </div>
                    <Button variant="ghost" size="icon" onClick={onClose} className="hover:bg-slate-800 text-slate-400 rounded-full">
                        <X className="w-5 h-5" />
                    </Button>
                </div>

                {/* Content */}
                <style>{scrollbarStyles}</style>
                <ScrollArea className="flex-1 overflow-hidden bg-slate-950/50 geek-scrollbar">
                    {loading ? (
                        <div className="flex-1 flex flex-col items-center justify-center h-full text-slate-500 gap-4 min-h-[400px]">
                            <Activity className="w-8 h-8 animate-spin text-blue-500" />
                            <span className="font-mono text-sm">获取数据中... (Retrieving Satellite Data...)</span>
                        </div>
                    ) : (
                        <Tabs defaultValue="steps" className="flex-1 flex flex-col overflow-hidden h-full">
                            <div className="px-6 pt-4 bg-slate-900/50 border-b border-slate-800 flex-shrink-0">
                                <TabsList className="bg-slate-950 border border-slate-800 mb-[-1px]">
                                    <TabsTrigger value="steps" className="text-slate-300 hover:text-white data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-300 data-[state=active]:border-b-2 data-[state=active]:border-purple-500 rounded-none transition-colors">
                                        瀑布流 (Timeline)
                                    </TabsTrigger>
                                    <TabsTrigger value="console" className="text-slate-300 hover:text-white data-[state=active]:bg-green-500/20 data-[state=active]:text-green-300 data-[state=active]:border-b-2 data-[state=active]:border-green-500 rounded-none transition-colors">
                                        控制台 (Terminal)
                                    </TabsTrigger>
                                    <TabsTrigger value="gallery" className="text-slate-300 hover:text-white data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-300 data-[state=active]:border-b-2 data-[state=active]:border-blue-500 rounded-none transition-colors">
                                        视觉画廊 (Gallery)
                                    </TabsTrigger>
                                </TabsList>
                            </div>

                            {/* Timeline / Steps Tab */}
                            <TabsContent value="steps" className="flex-1 overflow-hidden m-0 border-none outline-none">
                                <ScrollArea className="h-full bg-slate-950/50 geek-scrollbar">
                                    <div className="p-6 space-y-8">
                                        {data?.cases.map((tc) => (
                                            <div key={tc.tc_id} className="space-y-4">

                                                {/* Test Case Header */}
                                                <div className="flex items-center gap-3 mb-6">
                                                    <div className="p-2 bg-slate-900 rounded-lg border border-slate-800">
                                                        <StatusIcon status={tc.status} />
                                                    </div>
                                                    <div>
                                                        <h4 className="text-base font-medium text-slate-200">{tc.tc_id}</h4>
                                                        <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                                                            <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {tc.duration_ms.toFixed(0)}ms</span>
                                                            <span>•</span>
                                                            <span>{tc.steps.length} 步骤 (Steps)</span>
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Variable Trace Panel */}
                                                {tc.variable_trace && tc.variable_trace.length > 0 && (
                                                    <Collapsible className="mb-6 border border-slate-800 rounded-md bg-slate-900/30">
                                                        <CollapsibleTrigger className="flex items-center gap-2 p-3 w-full text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 transition-colors text-xs font-mono uppercase tracking-wider">
                                                            <Database className="w-3.5 h-3.5 text-purple-500" />
                                                            变量审计日志 (Variable Audit Log) ({tc.variable_trace.length})
                                                            <ChevronRight className="w-3 h-3 ml-auto transition-transform data-[state=open]:rotate-90" />
                                                        </CollapsibleTrigger>
                                                        <CollapsibleContent>
                                                            <div className="p-0">
                                                                <table className="w-full text-left text-xs font-mono">
                                                                    <thead className="bg-slate-900/80 text-slate-500 border-y border-slate-800">
                                                                        <tr>
                                                                            <th className="p-3 font-medium">变量 (Variable)</th>
                                                                            <th className="p-3 font-medium">值 (Value)</th>
                                                                            <th className="p-3 font-medium">源 (Source)</th>
                                                                        </tr>
                                                                    </thead>
                                                                    <tbody className="divide-y divide-slate-800/50">
                                                                        {tc.variable_trace.map((trace, idx) => (
                                                                            <tr key={idx} className="hover:bg-slate-800/30 transition-colors">
                                                                                <td className="p-3 text-purple-300 font-semibold">{trace.var_name}</td>
                                                                                <td className="p-3 text-slate-300 max-w-[200px] truncate" title={String(trace.value)}>{String(trace.value)}</td>
                                                                                <td className="p-3 text-slate-500">
                                                                                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700">
                                                                                        <span className="w-1.5 h-1.5 rounded-full bg-blue-500"></span>
                                                                                        步骤 (Step) {trace.source_step_index}
                                                                                    </span>
                                                                                </td>
                                                                            </tr>
                                                                        ))}
                                                                    </tbody>
                                                                </table>
                                                            </div>
                                                        </CollapsibleContent>
                                                    </Collapsible>
                                                )}



                                                {/* Steps Timeline */}
                                                <div className="relative space-y-2 pl-2">
                                                    {/* Timeline Line */}
                                                    <div className="absolute left-[19px] top-4 bottom-4 w-[2px] bg-slate-800/50" />

                                                    {tc.steps.map((step, idx) => {
                                                        const stepKey = `${tc.tc_id}-${idx}`;
                                                        const isOpen = openStepIndices.includes(stepKey);
                                                        const details = (step.details || {}) as StepDetail;

                                                        return (
                                                            <Collapsible
                                                                key={idx}
                                                                open={isOpen}
                                                                onOpenChange={() => toggleStep(stepKey)}
                                                                className="relative pl-10 group"
                                                            >
                                                                {/* Timeline Dot */}
                                                                <div className={cn(
                                                                    "absolute left-[14px] top-6 w-3 h-3 rounded-full border-2 z-10 transition-colors",
                                                                    details.warnings?.length ? "bg-amber-500 border-amber-900" :
                                                                        step.success ? "bg-green-500 border-green-900" : "bg-red-500 border-red-900",
                                                                    "group-hover:scale-110"
                                                                )} />

                                                                {/* Step Card */}
                                                                <div className={cn(
                                                                    "border rounded-lg bg-slate-900/40 transition-all duration-200 overflow-hidden",
                                                                    isOpen ? "border-slate-700 bg-slate-900/60 shadow-lg" : "border-slate-800 hover:border-slate-700"
                                                                )}>
                                                                    <CollapsibleTrigger className="w-full flex items-center justify-between p-4 cursor-pointer">
                                                                        <div className="flex items-center gap-3">
                                                                            <Badge variant="outline" className="font-mono text-[10px] text-slate-400 border-slate-700">
                                                                                步骤 (STEP) {step.step_index + 1}
                                                                            </Badge>
                                                                            {details.step_type === "UI" ? (
                                                                                <>
                                                                                    <Badge variant="outline" className="text-[10px] font-mono h-5 bg-indigo-500/20 text-indigo-300 border-indigo-500/50">UI</Badge>
                                                                                    <ActionBadge action={details.action_taken} />
                                                                                </>
                                                                            ) : (
                                                                                <MethodBadge method={details.request?.method} />
                                                                            )}
                                                                            <span className="text-sm font-mono text-slate-300 truncate max-w-[300px]" title={details.step_type === "UI" ? details.page_url : details.request?.url}>
                                                                                {details.step_name || "未知动作 (Unknown Action)"}
                                                                            </span>
                                                                        </div>

                                                                        <div className="flex items-center gap-4">
                                                                            {details.response && details.response.status > 0 && (
                                                                                <Badge variant={details.response.status >= 400 ? "destructive" : "secondary"} className="h-5 text-[10px]">
                                                                                    HTML {details.response.status}
                                                                                </Badge>
                                                                            )}
                                                                            <span className="text-xs font-mono text-slate-500">{step.duration_ms.toFixed(0)}ms</span>
                                                                            <ChevronRight className={cn("w-4 h-4 text-slate-500 transition-transform", isOpen && "rotate-90")} />
                                                                        </div>
                                                                    </CollapsibleTrigger>

                                                                    <CollapsibleContent>
                                                                        <div className="px-4 pb-4">
                                                                            {details.step_type === "UI" ? (
                                                                                /* UI Step View */
                                                                                <Tabs defaultValue="screenshot" className="w-full">
                                                                                    <TabsList className="grid w-full grid-cols-3 bg-slate-900 border border-slate-800 mb-4 h-9">
                                                                                        <TabsTrigger value="screenshot" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">截图 (Screenshot)</TabsTrigger>
                                                                                        <TabsTrigger value="action" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">动作与计划 (Action & Plan)</TabsTrigger>
                                                                                        <TabsTrigger value="page" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">页面信息 (Page Info)</TabsTrigger>
                                                                                    </TabsList>

                                                                                    <TabsContent value="screenshot" className="space-y-4 mt-0">
                                                                                        <div className="grid grid-cols-2 gap-4">
                                                                                            {details.screenshot_before && (
                                                                                                <div className="space-y-2">
                                                                                                    <span className="text-xs text-slate-500 font-mono block text-center">Before Action</span>
                                                                                                    <div className="rounded border border-slate-800 bg-slate-950 overflow-hidden relative group">
                                                                                                        {details.warnings?.some(w => w.type === 'VISION_ELEMENT_NOT_FOUND') && (
                                                                                                            <div className="absolute top-0 left-0 right-0 bg-red-900/90 text-red-100 p-2 text-[10px] font-mono border-b border-red-500 backdrop-blur-sm z-10 flex items-center gap-2">
                                                                                                                <Activity className="w-3 h-3 animate-pulse" />
                                                                                                                [!] AI Vision Agent could not locate the requested target in the current viewport.
                                                                                                            </div>
                                                                                                        )}
                                                                                                        <img src={details.screenshot_before} alt="Before" loading="lazy" className="w-full h-auto object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                                                                                    </div>
                                                                                                </div>
                                                                                            )}
                                                                                            {details.screenshot_after && (
                                                                                                <div className="space-y-2">
                                                                                                    <span className="text-xs text-slate-500 font-mono block text-center">After Action</span>
                                                                                                    <div className="rounded border border-slate-800 bg-slate-950 overflow-hidden relative group">
                                                                                                        <img src={details.screenshot_after} alt="After" loading="lazy" className="w-full h-auto object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                                                                                                    </div>
                                                                                                </div>
                                                                                            )}
                                                                                        </div>
                                                                                    </TabsContent>

                                                                                    <TabsContent value="action" className="space-y-4 mt-0">
                                                                                        <div className="grid grid-cols-2 gap-4">
                                                                                            <div className="space-y-1">
                                                                                                <h5 className="text-xs font-semibold text-slate-400">动作类型 (Action Type)</h5>
                                                                                                <ActionBadge action={details.action_taken} />
                                                                                            </div>
                                                                                            <div className="space-y-1">
                                                                                                <h5 className="text-xs font-semibold text-slate-400">策略 (Strategy)</h5>
                                                                                                <Badge variant="secondary" className="text-[10px] font-mono">{details.strategy || 'N/A'}</Badge>
                                                                                            </div>
                                                                                        </div>
                                                                                        <div className="space-y-2">
                                                                                            <h5 className="text-xs font-semibold text-slate-400">目标描述 (Target Description)</h5>
                                                                                            <div className="p-3 bg-[#0D1117] rounded border border-slate-800 font-mono text-xs text-purple-300">
                                                                                                {details.target_description || "无特定目标描述 (No specific target description)"}
                                                                                            </div>
                                                                                        </div>
                                                                                    </TabsContent>

                                                                                    <TabsContent value="page" className="space-y-4 mt-0">
                                                                                        <div className="space-y-2">
                                                                                            <h5 className="text-xs font-semibold text-slate-400">页面标题 (Page Title)</h5>
                                                                                            <div className="text-sm text-slate-200 font-medium">{details.page_title || "N/A"}</div>
                                                                                        </div>
                                                                                        <div className="space-y-2">
                                                                                            <h5 className="text-xs font-semibold text-slate-400">当前链接 (Current URL)</h5>
                                                                                            <div className="p-3 bg-[#0D1117] rounded border border-slate-800 font-mono text-xs text-slate-300 break-all">
                                                                                                {details.page_url || "N/A"}
                                                                                            </div>
                                                                                        </div>
                                                                                    </TabsContent>
                                                                                </Tabs>
                                                                            ) : (
                                                                                /* API Step View (Existing) */
                                                                                <Tabs defaultValue="response" className="w-full">
                                                                                    <TabsList className="grid w-full grid-cols-3 bg-slate-900 border border-slate-800 mb-4 h-9">
                                                                                        <TabsTrigger value="response" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">响应 (Response)</TabsTrigger>
                                                                                        <TabsTrigger value="request" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">请求 (Request)</TabsTrigger>
                                                                                        <TabsTrigger value="assertions" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">
                                                                                            断言 (Assertions)
                                                                                            {details.assertions_failed && details.assertions_failed.length > 0 && (
                                                                                                <span className="ml-2 w-1.5 h-1.5 rounded-full bg-red-500" />
                                                                                            )}
                                                                                        </TabsTrigger>
                                                                                    </TabsList>

                                                                                    <TabsContent value="response" className="space-y-3 mt-0">
                                                                                        {details.response?.headers && (
                                                                                            <div className="grid grid-cols-2 gap-2 mb-2">
                                                                                                {Object.entries(details.response.headers).map(([k, v]) => (
                                                                                                    <div key={k} className="flex gap-2 text-[10px]">
                                                                                                        <span className="text-slate-400 font-mono min-w-[80px] text-right truncate">{k}:</span>
                                                                                                        <span className="text-slate-300 font-mono truncate" title={String(v)}>{String(v)}</span>
                                                                                                    </div>
                                                                                                )).slice(0, 4)}
                                                                                            </div>
                                                                                        )}
                                                                                        <div className="bg-[#0D1117] p-3 rounded-md border border-slate-800 overflow-x-auto">
                                                                                            <pre className="text-[11px] font-mono text-slate-200 leading-relaxed">
                                                                                                {details.response ? (typeof details.response.body === 'string' ? details.response.body : JSON.stringify(details.response.body, null, 2)) : ""}
                                                                                            </pre>
                                                                                        </div>
                                                                                    </TabsContent>

                                                                                    <TabsContent value="request" className="space-y-4 mt-0">
                                                                                        <div className="space-y-2">
                                                                                            <h5 className="text-xs font-semibold text-slate-300">链接 (URL)</h5>
                                                                                            <div className="p-3 bg-[#0D1117] rounded border border-slate-800 font-mono text-xs text-slate-300 break-all">
                                                                                                {details.request?.url}
                                                                                            </div>
                                                                                        </div>
                                                                                        {details.request?.headers && Object.keys(details.request.headers).length > 0 && (
                                                                                            <div className="space-y-2">
                                                                                                <h5 className="text-xs font-semibold text-slate-300">请求头 (Headers)</h5>
                                                                                                <JsonViewer data={details.request.headers} />
                                                                                            </div>
                                                                                        )}
                                                                                        <div className="space-y-2">
                                                                                            <h5 className="text-xs font-semibold text-slate-300">请求体 (Body)</h5>
                                                                                            <JsonViewer data={details.request?.body} />
                                                                                        </div>
                                                                                    </TabsContent>

                                                                                    <TabsContent value="assertions" className="space-y-2 mt-0">
                                                                                        {details.assertions_failed && details.assertions_failed.length > 0 ? (
                                                                                            <div className="space-y-2">
                                                                                                {details.assertions_failed.map((fail: string, i: number) => (
                                                                                                    <div key={i} className="flex items-start gap-2 p-3 bg-red-950/20 border border-red-900/30 rounded text-red-300 text-xs font-mono">
                                                                                                        <XCircle className="w-3 h-3 mt-0.5 shrink-0" />
                                                                                                        {fail}
                                                                                                    </div>
                                                                                                ))}
                                                                                            </div>
                                                                                        ) : (
                                                                                            <div className="flex flex-col items-center justify-center p-8 text-slate-500 gap-2">
                                                                                                <CheckCircle className="w-8 h-8 text-green-500/40" />
                                                                                                <span className="text-xs text-green-500">所有断言均通过 (All assertions passed)</span>
                                                                                            </div>
                                                                                        )}
                                                                                    </TabsContent>
                                                                                </Tabs>
                                                                            )}

                                                                            {/* Extracted Values Badge */}
                                                                            {details.extracted && Object.keys(details.extracted).length > 0 && (
                                                                                <div className="mt-4 pt-3 border-t border-slate-800/50">
                                                                                    <div className="flex flex-wrap gap-2">
                                                                                        {Object.entries(details.extracted).map(([k, v]) => (
                                                                                            <div key={k} className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 border border-purple-500/30 rounded text-xs text-purple-300 font-mono shadow-sm">
                                                                                                <Database className="w-3.5 h-3.5 text-purple-400" />
                                                                                                <span className="opacity-70">提取变量 (Extracted):</span>
                                                                                                <span className="font-semibold text-purple-200">{k}</span>
                                                                                                <span className="opacity-50 mx-1">=</span>
                                                                                                <span className="font-semibold truncate max-w-[150px]" title={String(v)}>{String(v)}</span>
                                                                                            </div>
                                                                                        ))}
                                                                                    </div>
                                                                                </div>
                                                                            )}
                                                                        </div>
                                                                    </CollapsibleContent>
                                                                </div>
                                                            </Collapsible>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </ScrollArea>
                            </TabsContent>

                            {/* Terminal / Console Tab */}
                            <TabsContent value="console" className="flex-1 overflow-hidden m-0 border-none outline-none bg-[#0D1117] p-6 relative group">
                                <div className="absolute top-2 right-4 text-[10px] text-green-500/50 font-mono uppercase tracking-widest">Live Output</div>
                                <ScrollArea className="h-full geek-scrollbar pr-4">
                                    <div className="font-mono text-[11px] leading-relaxed">
                                        <div className="text-green-500 mb-4">{`> Setting up execution environment for ${executionId}...`}</div>
                                        <div className="text-slate-400 mb-4">{`> Connecting to remote workers [OK]`}</div>
                                        {data?.cases.map((tc) => (
                                            <div key={tc.tc_id} className="mb-6">
                                                <div className="text-blue-400 font-bold tracking-wide">{`[SYSTEM] Starting Test Case Pipeline: ${tc.tc_id}`}</div>
                                                <div className="ml-2 border-l border-slate-800 pl-4 mt-2 space-y-1">
                                                    {tc.steps.map((step, i) => {
                                                        const details = (step.details || {}) as StepDetail;
                                                        const isFail = !step.success;
                                                        return (
                                                            <div key={i} className={`flex flex-col gap-1 ${isFail ? 'text-red-400' : 'text-slate-300'}`}>
                                                                <div className="flex items-center gap-2">
                                                                    <span className="text-slate-600">[{new Date(Date.now() - tc.duration_ms + step.duration_ms).toISOString().split('T')[1].slice(0, 12)}]</span>
                                                                    <span className={cn("px-1.5 py-0.5 rounded text-[9px] uppercase", details?.step_type === 'UI' ? 'bg-indigo-500/20 text-indigo-400' : 'bg-cyan-500/20 text-cyan-400')}>
                                                                        {details?.step_type || 'SYS'}
                                                                    </span>
                                                                    <span>{`Step ${step.step_index + 1}:`}</span>
                                                                    <span>{details?.step_name || 'Action'}</span>
                                                                    <span className="text-slate-500">...</span>
                                                                    <span className={isFail ? 'text-red-500 font-bold' : 'text-green-500'}>
                                                                        {isFail ? 'FAILED' : 'SUCCESS'}
                                                                    </span>
                                                                    <span className="text-slate-600">({step.duration_ms}ms)</span>
                                                                </div>
                                                                {isFail && step.error && <div className="ml-8 text-red-500 break-words font-medium">{`>> Error: ${step.error}`}</div>}
                                                                {details?.warnings?.map((w, wi) => (
                                                                    <div key={wi} className="ml-8 text-amber-500">{`>> [WARN] ${w.type}: ${w.message}`}</div>
                                                                ))}
                                                                {details?.extracted && Object.keys(details.extracted).length > 0 && (
                                                                    <div className="ml-8 text-purple-400">{`>> [EXTRACT] Exported ${Object.keys(details.extracted).length} variables context`}</div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                                <div className="text-blue-400 mt-2 font-bold">{`[SYSTEM] Completed Test Case Pipeline: ${tc.tc_id} in ${tc.duration_ms}ms`}</div>
                                            </div>
                                        ))}
                                        {!hasCaseResults && isActiveExecution && (
                                            <div className="mt-4 space-y-2 text-amber-400">
                                                <div>{`> Execution status: ${data?.status || "pending"}`}</div>
                                                <div className="text-slate-400">{`> Waiting for worker output...`}</div>
                                            </div>
                                        )}
                                        {!hasCaseResults && !isActiveExecution && isFailedExecution && (
                                            <div className="mt-4 space-y-2 text-red-400">
                                                <div>{`> Execution status: ${data?.status || "failed"}`}</div>
                                                <div className="text-slate-400">{`> No step result was persisted for this execution.`}</div>
                                            </div>
                                        )}
                                        {!hasCaseResults && !isActiveExecution && !isFailedExecution && (
                                            <div className="mt-4 space-y-2 text-slate-400">
                                                <div>{`> Execution status: ${data?.status || "unknown"}`}</div>
                                                <div>{`> No detailed step output is available yet.`}</div>
                                            </div>
                                        )}
                                        {hasCaseResults && (
                                            <div className={cn(
                                                "flex items-center gap-2 mt-4",
                                                isFailedExecution ? "text-red-500" : "text-green-500"
                                            )}>
                                                <span>{`> Process exited with code ${isFailedExecution ? 1 : 0}`}</span>
                                                <div className={cn(
                                                    "w-2 h-4",
                                                    isFailedExecution ? "bg-red-500" : "bg-green-500 animate-pulse"
                                                )} />
                                            </div>
                                        )}
                                    </div>
                                </ScrollArea>
                            </TabsContent>

                            {/* Gallery Tab */}
                            <TabsContent value="gallery" className="flex-1 overflow-hidden m-0 border-none outline-none p-6 bg-slate-950">
                                <ScrollArea className="h-full geek-scrollbar pr-4">
                                    <div className="grid grid-cols-2 gap-6">
                                        {data?.cases.flatMap(tc => tc.steps.filter(s => s.details?.screenshot_before || s.details?.screenshot_after).map((s, i) => (
                                            <div key={`${tc.tc_id}-${i}`} className="border border-slate-800 bg-slate-900 rounded-xl p-4 space-y-3 shadow-lg group hover:border-blue-500/50 transition-colors">
                                                <div className="flex flex-col">
                                                    <Badge variant="outline" className="w-fit text-[10px] font-mono mb-1 bg-slate-800 text-slate-400 border-none">{`${tc.tc_id} - Step ${s.step_index + 1}`}</Badge>
                                                    <span className="text-sm font-medium text-slate-200 truncate" title={s.details?.step_name}>{s.details?.step_name}</span>
                                                </div>
                                                <div className="grid grid-cols-2 gap-3 mt-2 relative">
                                                    {s.details?.screenshot_before && (
                                                        <div className="space-y-1.5 flex flex-col items-center">
                                                            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest bg-slate-950 px-2 py-0.5 rounded-full border border-slate-800">Before</span>
                                                            <img src={s.details.screenshot_before} alt={`${tc.tc_id} step ${s.step_index + 1} before`} className="rounded-md border border-slate-700 w-full object-cover aspect-video hover:scale-[1.02] transition-transform cursor-crosshair shadow-md" loading="lazy" />
                                                        </div>
                                                    )}
                                                    {s.details?.screenshot_after && (
                                                        <div className="space-y-1.5 flex flex-col items-center">
                                                            <span className="text-[10px] font-mono text-slate-500 uppercase tracking-widest bg-slate-950 px-2 py-0.5 rounded-full border border-slate-800">After</span>
                                                            <img src={s.details.screenshot_after} alt={`${tc.tc_id} step ${s.step_index + 1} after`} className="rounded-md border border-slate-700 w-full object-cover aspect-video hover:scale-[1.02] transition-transform cursor-crosshair shadow-md" loading="lazy" />
                                                        </div>
                                                    )}
                                                    {s.details?.screenshot_before && s.details?.screenshot_after && (
                                                        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 mt-3 bg-slate-800 p-1.5 rounded-full shadow-lg border border-slate-700 z-10 group-hover:scale-110 transition-transform">
                                                            <ArrowRight className="w-4 h-4 text-blue-400" />
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        )))}
                                        {(!data || data.cases.every(tc => !tc.steps.some(s => s.details?.screenshot_before || s.details?.screenshot_after))) && (
                                            <div className="col-span-2 flex flex-col items-center py-20 text-slate-500 space-y-4">
                                                <div className="w-16 h-16 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center">
                                                    <XCircle className="w-8 h-8 text-slate-600" />
                                                </div>
                                                <span className="font-mono text-sm tracking-wide">无视觉资产捕获 (NO VISUAL ASSETS CAPTURED)</span>
                                                <span className="text-xs max-w-sm text-center opacity-60">仅针对UI操作捕获截图。API测试或失败的准备工作不生成图像。 (Screenshots are only captured for UI actions. API tests or failed preparations do not produce images.)</span>
                                            </div>
                                        )}
                                    </div>
                                </ScrollArea>
                            </TabsContent>
                        </Tabs>
                    )}
                </ScrollArea>
            </div>
        </>
    );
}

