"use client";

import { X, CheckCircle, XCircle, Clock, Terminal, ChevronRight, Activity, ArrowRight, Database } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
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
        headers: any;
        body: any;
    };
    response?: {
        status: number;
        headers: any;
        body: any;
    };
    extracted?: Record<string, any>;
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
        details?: any;
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
        value: any;
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

    // Toast Trigger for Vision Failures
    useEffect(() => {
        if (!data) return;
        data.cases.forEach(tc => {
            tc.steps.forEach(step => {
                const stepId = `${tc.tc_id}-${step.step_index}`;
                const details = step.details as StepDetail;
                if (details?.warnings?.some(w => w.type === 'VISION_ELEMENT_NOT_FOUND') && !toastedSteps.current.has(stepId)) {
                    toast.warning("⚠️ 视觉感知未命中", {
                        description: `当前页面截图中未找到目标元素 [${details.target_description || 'Unknown'}], 已终止或降级。`,
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
        if (open && executionId) {
            setLoading(true);
            fetch(`/api/v1/executions/${executionId}/steps`)
                .then(res => res.json())
                .then(data => {
                    setData(data);
                })
                .catch(err => console.error(err))
                .finally(() => setLoading(false));
        } else {
            setData(null);
            setOpenStepIndices([]);
        }
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

    const JsonViewer = ({ data }: { data: any }) => {
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
                            Full Execution Inspector
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
                        <div className="flex flex-col items-center justify-center h-64 text-slate-500 gap-4">
                            <Activity className="w-8 h-8 animate-spin text-blue-500" />
                            <span className="font-mono text-sm">Retrieving Satellite Data...</span>
                        </div>
                    ) : (
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
                                                <span>{tc.steps.length} Steps</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Variable Trace Panel */}
                                    {tc.variable_trace && tc.variable_trace.length > 0 && (
                                        <Collapsible className="mb-6 border border-slate-800 rounded-md bg-slate-900/30">
                                            <CollapsibleTrigger className="flex items-center gap-2 p-3 w-full text-slate-400 hover:text-slate-200 hover:bg-slate-900/50 transition-colors text-xs font-mono uppercase tracking-wider">
                                                <Database className="w-3.5 h-3.5 text-purple-500" />
                                                Variable Audit Log ({tc.variable_trace.length})
                                                <ChevronRight className="w-3 h-3 ml-auto transition-transform data-[state=open]:rotate-90" />
                                            </CollapsibleTrigger>
                                            <CollapsibleContent>
                                                <div className="p-0">
                                                    <table className="w-full text-left text-xs font-mono">
                                                        <thead className="bg-slate-900/80 text-slate-500 border-y border-slate-800">
                                                            <tr>
                                                                <th className="p-3 font-medium">Variable</th>
                                                                <th className="p-3 font-medium">Value</th>
                                                                <th className="p-3 font-medium">Source</th>
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
                                                                            Step {trace.source_step_index}
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
                                                                    STEP {step.step_index + 1}
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
                                                                    {details.step_name || "Unknown Action"}
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
                                                                            <TabsTrigger value="screenshot" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">Screenshot</TabsTrigger>
                                                                            <TabsTrigger value="action" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">Action & Plan</TabsTrigger>
                                                                            <TabsTrigger value="page" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white">Page Info</TabsTrigger>
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
                                                                                    <h5 className="text-xs font-semibold text-slate-400">Action Type</h5>
                                                                                    <ActionBadge action={details.action_taken} />
                                                                                </div>
                                                                                <div className="space-y-1">
                                                                                    <h5 className="text-xs font-semibold text-slate-400">Strategy</h5>
                                                                                    <Badge variant="secondary" className="text-[10px] font-mono">{details.strategy || 'N/A'}</Badge>
                                                                                </div>
                                                                            </div>
                                                                            <div className="space-y-2">
                                                                                <h5 className="text-xs font-semibold text-slate-400">Target Description</h5>
                                                                                <div className="p-3 bg-[#0D1117] rounded border border-slate-800 font-mono text-xs text-purple-300">
                                                                                    {details.target_description || "No specific target description"}
                                                                                </div>
                                                                            </div>
                                                                        </TabsContent>

                                                                        <TabsContent value="page" className="space-y-4 mt-0">
                                                                            <div className="space-y-2">
                                                                                <h5 className="text-xs font-semibold text-slate-400">Page Title</h5>
                                                                                <div className="text-sm text-slate-200 font-medium">{details.page_title || "N/A"}</div>
                                                                            </div>
                                                                            <div className="space-y-2">
                                                                                <h5 className="text-xs font-semibold text-slate-400">Current URL</h5>
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
                                                                            <TabsTrigger value="response" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">Response</TabsTrigger>
                                                                            <TabsTrigger value="request" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">Request</TabsTrigger>
                                                                            <TabsTrigger value="assertions" className="text-xs data-[state=active]:bg-slate-800 data-[state=active]:text-white data-[state=inactive]:text-slate-400">
                                                                                Assertions
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
                                                                                    {details.response && (typeof details.response.body === 'object' ? JSON.stringify(details.response.body, null, 2) : details.response.body)}
                                                                                </pre>
                                                                            </div>
                                                                        </TabsContent>

                                                                        <TabsContent value="request" className="space-y-4 mt-0">
                                                                            <div className="space-y-2">
                                                                                <h5 className="text-xs font-semibold text-slate-300">URL</h5>
                                                                                <div className="p-3 bg-[#0D1117] rounded border border-slate-800 font-mono text-xs text-slate-300 break-all">
                                                                                    {details.request?.url}
                                                                                </div>
                                                                            </div>
                                                                            {details.request?.headers && Object.keys(details.request.headers).length > 0 && (
                                                                                <div className="space-y-2">
                                                                                    <h5 className="text-xs font-semibold text-slate-300">Headers</h5>
                                                                                    <JsonViewer data={details.request.headers} />
                                                                                </div>
                                                                            )}
                                                                            <div className="space-y-2">
                                                                                <h5 className="text-xs font-semibold text-slate-300">Body</h5>
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
                                                                                    <span className="text-xs text-green-500">All assertions passed</span>
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
                                                                                    <span className="opacity-70">提取变量:</span>
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
                    )}
                </ScrollArea>
            </div>
        </>
    );
}

