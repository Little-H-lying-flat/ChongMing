"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw, Play, Activity, Trash2 } from "lucide-react";
import { ExecutionDrawer } from "@/components/ui/execution-drawer";
import api from "@/services/api";
import { Environment, getEnvironments } from "@/services/environmentService";

import { Button } from "@/components/ui/button";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Types
interface ExecutionStatus {
    execution_id: string;
    status: string;
    progress: number;
    passed: number;
    failed: number;
    skipped: number;
    running: number;
    pending: number;
    start_time: string;
    elapsed_seconds: number;
}

interface ExecutionRequest {
    tc_ids: string[];
    mode: string;
    parallel: boolean;
    max_workers: number;
    env?: string;
}

// API Functions
const fetchExecutions = async (page: number): Promise<{ total: number, items: ExecutionStatus[] }> => {
    const skip = (page - 1) * 20;
    const res = await api.fetch(`/executions?skip=${skip}&limit=20`);
    if (!res.ok) throw new Error("Failed to fetch executions");
    return res.json();
};

const fetchStats = async () => {
    const res = await api.fetch("/executions/stats");
    if (!res.ok) throw new Error("Failed to fetch stats");
    return res.json();
};

const deleteExecution = async (executionId: string) => {
    const res = await api.fetch(`/executions/${executionId}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete execution");
    return res.json();
};

const fetchTestCases = async () => {
    const res = await api.fetch("/test-cases?page=1&page_size=100");
    if (!res.ok) throw new Error("Failed to fetch test cases");
    return res.json();
};

const startExecution = async (data: ExecutionRequest) => {
    const res = await api.fetch("/executions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Failed to start execution");
    return res.json();
};

export default function ExecutionsPage() {
    const queryClient = useQueryClient();
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    // Drawer State
    const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
    const [executionToDelete, setExecutionToDelete] = useState<string | null>(null);

    // Form State
    const [selectedTcIds, setSelectedTcIds] = useState<string[]>([]);
    const [mode, setMode] = useState("normal");
    const [parallel, setParallel] = useState(true);
    const [maxWorkers] = useState(5);
    const [env, setEnv] = useState("default");

    const [currentPage, setCurrentPage] = useState(1);

    // Query
    const { data: executionsData } = useQuery({
        queryKey: ["executions", currentPage],
        queryFn: () => fetchExecutions(currentPage),
        refetchInterval: 2000, // Poll every 2s
    });

    const { data: statsData } = useQuery({
        queryKey: ["executionStats"],
        queryFn: fetchStats,
        refetchInterval: 5000,
    });

    const { data: tcData } = useQuery({
        queryKey: ["testcases"],
        queryFn: fetchTestCases,
    });

    const { data: environments = [] } = useQuery<Environment[]>({
        queryKey: ["environments", "active"],
        queryFn: () => getEnvironments(true),
    });

    const executions = executionsData?.items || [];
    const total = executionsData?.total || 0;
    const totalPages = Math.ceil(total / 20) || 1;

    // Mutation
    const mutation = useMutation({
        mutationFn: startExecution,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["executions"] });
            setIsDialogOpen(false);
        },
    });

    const deleteMutation = useMutation({
        mutationFn: deleteExecution,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["executions"] });
            queryClient.invalidateQueries({ queryKey: ["executionStats"] });
            setExecutionToDelete(null);
        },
    });

    const handleDelete = (e: React.MouseEvent, executionId: string) => {
        e.stopPropagation();
        setExecutionToDelete(executionId);
    };

    const confirmDelete = () => {
        if (executionToDelete) {
            deleteMutation.mutate(executionToDelete);
        }
    };

    const handleStart = () => {
        if (selectedTcIds.length === 0) return;
        mutation.mutate({
            tc_ids: selectedTcIds,
            mode,
            parallel,
            max_workers: Number(maxWorkers),
            env: env === "default" ? undefined : env,
        });
    };

    const toggleTcSelection = (tcId: string) => {
        setSelectedTcIds(prev =>
            prev.includes(tcId)
                ? prev.filter(id => id !== tcId)
                : [...prev, tcId]
        );
    };

    const selectAllTcs = () => {
        if (!tcData?.items) return;
        if (selectedTcIds.length === tcData.items.length) {
            setSelectedTcIds([]); // Deselect all
        } else {
            setSelectedTcIds(tcData.items.map((tc: { id: string }) => tc.id));
        }
    };

    const StatusBadge = ({ status }: { status: string }) => {
        const s = status.toLowerCase();
        const base = "px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-sm transition-all duration-300";
        if (s === "passed") {
            return <div className={`${base} bg-green-500/10 border-green-500/30 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.15)]`}>{status}</div>;
        } else if (s === "failed") {
            return <div className={`${base} bg-rose-50 border-rose-200 text-rose-700 shadow-[0_0_10px_rgba(239,68,68,0.15)]`}>{status}</div>;
        } else if (s === "running") {
            return <div className={`${base} bg-sky-50 border-sky-200 text-sky-700 shadow-[0_0_15px_rgba(59,130,246,0.25)] animate-pulse`}>{status}</div>;
        } else if (s === "pending") {
            return <div className={`${base} bg-amber-50 border-amber-200 text-amber-700`}>{status}</div>;
        }
        return <div className={`${base} bg-slate-100 border-slate-200 text-slate-600`}>{status}</div>;
    };

    const handleRowClick = (executionId: string) => {
        setSelectedExecutionId(executionId);
    };

    // ... existing render ...

    return (
        <div className="space-y-6">

            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight text-slate-900">调度大盘 (Dispatch Dashboard)</h1>
                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                        <Button className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600 border-transparent">
                            <Play className="w-4 h-4 mr-2" />
                            Run Regression (回归测试)
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="rounded-2xl border-sky-100 bg-white/80 text-slate-900 sm:max-w-[600px] max-h-[85vh] flex flex-col pt-8">
                        <DialogHeader className="mb-4">
                            <DialogTitle className="text-xl font-semibold flex items-center gap-2">
                                <Activity className="w-5 h-5 text-sky-600" />
                                执行回归 (Run Regression)
                            </DialogTitle>
                            <DialogDescription className="text-slate-600">
                                选择系统中的测试用例发起回归执行。 (Select test cases in the system to run regression.)
                            </DialogDescription>
                        </DialogHeader>

                        <div className="flex-1 overflow-y-auto pr-2 space-y-6 custom-scrollbar">
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <Label className="text-sm font-medium text-slate-800">选择用例 (Select Test Cases)</Label>
                                    <Button variant="ghost" size="sm" onClick={selectAllTcs} className="text-sky-700 hover:text-sky-800 hover:bg-sky-50 h-7 text-xs px-2">
                                        {tcData?.items && selectedTcIds.length === tcData.items.length ? "取消全选 (Deselect All)" : "全选全部 (Select All)"}
                                    </Button>
                                </div>
                                <div className="border border-sky-100 rounded-lg bg-white p-2 h-[240px] overflow-y-auto mb-2 custom-scrollbar">
                                    {(!tcData?.items || tcData.items.length === 0) ? (
                                        <div className="text-center text-slate-500 py-10 text-sm">暂无存量测试用例 (No test cases found)</div>
                                    ) : (
                                        tcData.items.map((tc: { id: string; name: string; mode?: string }) => (
                                            <div key={tc.id} className="flex items-center gap-3 p-2.5 hover:bg-sky-50/50 rounded-md transition-colors cursor-pointer group" onClick={() => toggleTcSelection(tc.id)}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedTcIds.includes(tc.id)}
                                                    onChange={() => { }}
                                                    className="w-4 h-4 rounded bg-white/80 border-sky-200 text-blue-500 focus:ring-blue-500 focus:ring-offset-white cursor-pointer pointer-events-none"
                                                />
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-mono text-slate-600">{tc.id}</span>
                                                        <span className="text-sm text-slate-800 font-medium truncate group-hover:text-sky-700 transition-colors">{tc.name}</span>
                                                    </div>
                                                </div>
                                                {tc.mode === 'UI' ? (
                                                    <Badge className="bg-violet-50 text-violet-700 border-violet-200 text-[10px] px-1.5 py-0">UI</Badge>
                                                ) : tc.mode === 'API' ? (
                                                    <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-[10px] px-1.5 py-0">API</Badge>
                                                ) : (
                                                    <Badge className="bg-sky-50 text-sky-700 border-sky-200 text-[10px] px-1.5 py-0">HYBRID</Badge>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                                <div className="text-xs text-slate-500 text-right">已选择: {selectedTcIds.length}个用例 (Selected: {selectedTcIds.length} cases)</div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-slate-700">执行模式 (Execution Mode)</Label>
                                    <Select value={mode} onValueChange={setMode}>
                                        <SelectTrigger className="bg-white/80 border-sky-200 h-9">
                                            <SelectValue placeholder="Select mode" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-white/80 border-sky-200">
                                            <SelectItem value="normal" className="focus:bg-sky-50">普通执行 (Normal Execution)</SelectItem>
                                            <SelectItem value="debug" className="focus:bg-sky-50">调试执行 (Debug Execution)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-slate-700">环境 (Environment)</Label>
                                    <Select value={env} onValueChange={setEnv}>
                                        <SelectTrigger className="bg-white/80 border-sky-200 h-9">
                                            <SelectValue placeholder="选择环境 (Select environment)" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-white/80 border-sky-200">
                                            <SelectItem value="default" className="focus:bg-sky-50">默认环境 (Default)</SelectItem>
                                            {environments.map((environment) => (
                                                <SelectItem key={environment.id} value={environment.id} className="focus:bg-sky-50">
                                                    {environment.name}{environment.is_default ? " · 默认" : ""}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="flex items-center justify-between p-3 bg-white/80 rounded-lg border border-sky-100/50">
                                <div className="space-y-0.5">
                                    <Label className="text-slate-800 text-sm">并行执行 (Parallel Execution)</Label>
                                    <p className="text-xs text-slate-500">启用Celery并发，加速长列表测试 (Enable Celery concurrency to accelerate tests)</p>
                                </div>
                                <Switch checked={parallel} onCheckedChange={setParallel} className="data-[state=checked]:bg-blue-500" />
                            </div>
                        </div>

                        <DialogFooter className="mt-6 border-t border-sky-100 pt-4 flex-shrink-0">
                            <Button variant="outline" onClick={() => setIsDialogOpen(false)} className="border-sky-200 bg-transparent text-slate-700 hover:bg-sky-50">
                                取消 (Cancel)
                            </Button>
                            <Button onClick={handleStart} disabled={mutation.isPending || selectedTcIds.length === 0} className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600 min-w-[120px]">
                                {mutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                                执行回归 (Run Regression)
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Metrics Header */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600">执行总数 (Total Executions)</CardTitle>
                        <Activity className="h-4 w-4 text-slate-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-900">{statsData?.total || 0}</div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600">运行中任务 (Active Tasks)</CardTitle>
                        <RefreshCw className={`h-4 w-4 text-sky-600 ${statsData?.active > 0 ? 'animate-spin' : ''}`} />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-900">{statsData?.active || 0}</div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none" />
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600">成功率 (Success Rate)</CardTitle>
                        <Activity className="h-4 w-4 text-green-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-900 flex items-baseline gap-1">
                            {statsData?.success_rate || 0}
                            <span className="text-base text-slate-500">%</span>
                        </div>
                    </CardContent>
                </Card>
                <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-600">平均耗时 (Avg Duration)</CardTitle>
                        <Loader2 className="h-4 w-4 text-violet-600" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-900 flex items-baseline gap-1">
                            {statsData?.avg_duration || 0}
                            <span className="text-base text-slate-500">s</span>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card className="rounded-2xl border-sky-100 bg-white/80">
                {/* ... existing card header ... */}
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow className="border-sky-100 hover:bg-transparent">
                                <TableHead className="text-slate-800">执行ID (Execution ID)</TableHead>
                                <TableHead className="text-slate-800">状态 (Status)</TableHead>
                                <TableHead className="text-slate-800">进度 (Progress)</TableHead>
                                <TableHead className="text-slate-800 text-right">通过 / 失败 (Pass / Fail)</TableHead>
                                <TableHead className="text-slate-800 text-right">耗时 (Elapsed)</TableHead>
                                <TableHead className="text-slate-800 text-right w-[80px]">操作 (Actions)</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {executions?.map((exec) => (
                                <TableRow
                                    key={exec.execution_id}
                                    className="border-sky-100 hover:bg-sky-50/50 cursor-pointer transition-colors"
                                    onClick={() => handleRowClick(exec.execution_id)}
                                >
                                    <TableCell className="font-mono text-xs text-slate-800">{exec.execution_id}</TableCell>
                                    <TableCell>
                                        <StatusBadge status={exec.status} />
                                    </TableCell>
                                    <TableCell className="w-[200px]">
                                        <div className="flex items-center gap-3">
                                            <div className="relative w-full h-2 bg-sky-50 rounded-full overflow-hidden shrink-0">
                                                <div
                                                    className={`absolute top-0 left-0 h-full rounded-full transition-all duration-500 ${exec.status.toLowerCase() === 'running' ? 'bg-gradient-to-r from-blue-500 via-indigo-400 to-blue-500 bg-[length:200%_100%] animate-pulse' : exec.status.toLowerCase() === 'failed' ? 'bg-red-500' : 'bg-green-500'}`}
                                                    style={{ width: `${Math.round(exec.progress)}%` }}
                                                />
                                            </div>
                                            <span className="text-xs text-slate-700 w-10 text-right font-mono">{Math.round(exec.progress)}%</span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <span className="text-green-400 font-medium">{exec.passed}</span>
                                        <span className="text-slate-600 mx-1">/</span>
                                        <span className="text-rose-700 font-medium">{exec.failed}</span>
                                    </TableCell>
                                    <TableCell className="text-right text-slate-800 font-mono">
                                        {exec.elapsed_seconds.toFixed(1)}s
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-600 hover:text-rose-700 hover:bg-red-500/10 transition-colors"
                                            onClick={(e) => handleDelete(e, exec.execution_id)}
                                            disabled={deleteMutation.isPending}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            ))}
                            {/* ... empty state could be handled here ... */}
                        </TableBody>
                    </Table>

                    {/* Pagination */}
                    <div className="flex items-center justify-between pt-4 border-t border-sky-100/50 mt-4">
                        <p className="text-sm text-slate-600">
                            Showing <span className="font-medium text-slate-800">{executions.length}</span> of{" "}
                            <span className="font-medium text-slate-800">{total}</span> executions
                        </p>
                        <div className="flex items-center space-x-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="border-sky-200 bg-white/80 text-slate-700 hover:bg-sky-50 hover:text-slate-900 h-8"
                            >
                                上一页 (Previous)
                            </Button>
                            <span className="text-sm text-slate-600 min-w-[3rem] text-center font-mono">
                                {currentPage} / {totalPages}
                            </span>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="border-sky-200 bg-white/80 text-slate-700 hover:bg-sky-50 hover:text-slate-900 h-8"
                            >
                                下一页 (Next)
                            </Button>
                        </div>
                    </div>
                </CardContent>
            </Card>

            <ExecutionDrawer
                executionId={selectedExecutionId}
                open={!!selectedExecutionId}
                onClose={() => setSelectedExecutionId(null)}
            />

            {/* Delete Confirmation Dialog */}
            <Dialog open={!!executionToDelete} onOpenChange={(open) => !open && setExecutionToDelete(null)}>
                <DialogContent className="rounded-2xl border-sky-100 bg-white/80 text-slate-800">
                    <DialogHeader>
                        <DialogTitle>删除执行记录 (Delete Execution Record)</DialogTitle>
                        <DialogDescription className="text-slate-600">
                            确定要删除这条执行记录吗？相关联的测试记录和截图将被永久清理，此操作不可恢复。 (Are you sure you want to delete this execution? Associated test records and screenshots will be permanently removed.)
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="ghost" onClick={() => setExecutionToDelete(null)} disabled={deleteMutation.isPending}>
                            取消 (Cancel)
                        </Button>
                        <Button variant="destructive" onClick={confirmDelete} disabled={deleteMutation.isPending}>
                            {deleteMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : "确定删除 (Confirm Delete)"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}

