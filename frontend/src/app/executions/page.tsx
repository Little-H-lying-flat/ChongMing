"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Loader2, RefreshCw, Play, Activity, Trash2 } from "lucide-react";
import { format } from "date-fns";
import { ExecutionDrawer } from "@/components/ui/execution-drawer";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
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
    const res = await fetch(`/api/v1/executions?skip=${skip}&limit=20`);
    if (!res.ok) throw new Error("Failed to fetch executions");
    return res.json();
};

const fetchStats = async () => {
    const res = await fetch("/api/v1/executions/stats");
    if (!res.ok) throw new Error("Failed to fetch stats");
    return res.json();
};

const deleteExecution = async (executionId: string) => {
    const res = await fetch(`/api/v1/executions/${executionId}`, {
        method: "DELETE",
    });
    if (!res.ok) throw new Error("Failed to delete execution");
    return res.json();
};

const fetchTestCases = async () => {
    const res = await fetch("/api/v1/test-cases?page=1&page_size=100");
    if (!res.ok) throw new Error("Failed to fetch test cases");
    return res.json();
};

const startExecution = async (data: ExecutionRequest) => {
    const res = await fetch("/api/v1/executions", {
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
    const [maxWorkers, setMaxWorkers] = useState(5);
    const [env, setEnv] = useState("dev");

    const [currentPage, setCurrentPage] = useState(1);

    // Query
    const { data: executionsData, isLoading, isError } = useQuery({
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
            env,
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
            setSelectedTcIds(tcData.items.map((tc: any) => tc.id));
        }
    };

    const StatusBadge = ({ status }: { status: string }) => {
        const s = status.toLowerCase();
        const base = "px-2.5 py-0.5 rounded-full text-xs font-medium border backdrop-blur-sm transition-all duration-300";
        if (s === "passed") {
            return <div className={`${base} bg-green-500/10 border-green-500/30 text-green-400 shadow-[0_0_10px_rgba(34,197,94,0.15)]`}>{status}</div>;
        } else if (s === "failed") {
            return <div className={`${base} bg-red-500/10 border-red-500/30 text-red-400 shadow-[0_0_10px_rgba(239,68,68,0.15)]`}>{status}</div>;
        } else if (s === "running") {
            return <div className={`${base} bg-blue-500/10 border-blue-500/30 text-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.25)] animate-pulse`}>{status}</div>;
        } else if (s === "pending") {
            return <div className={`${base} bg-amber-500/10 border-amber-500/30 text-amber-400`}>{status}</div>;
        }
        return <div className={`${base} bg-slate-500/10 border-slate-500/30 text-slate-400`}>{status}</div>;
    };

    const handleRowClick = (executionId: string) => {
        setSelectedExecutionId(executionId);
    };

    // ... existing render ...

    return (
        <div className="space-y-6">

            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold tracking-tight text-slate-100">调度大盘 (Dispatch Dashboard)</h1>
                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                        <Button className="bg-blue-600 hover:bg-blue-700 text-white border-transparent shadow-lg shadow-blue-900/20">
                            <Play className="w-4 h-4 mr-2" />
                            Run Regression (回归测试)
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="bg-slate-900 border-slate-800 text-slate-100 sm:max-w-[600px] max-h-[85vh] flex flex-col pt-8">
                        <DialogHeader className="mb-4">
                            <DialogTitle className="text-xl font-semibold flex items-center gap-2">
                                <Activity className="w-5 h-5 text-blue-400" />
                                执行回归 (Run Regression)
                            </DialogTitle>
                            <DialogDescription className="text-slate-400">
                                选择系统中的测试用例发起回归执行。 (Select test cases in the system to run regression.)
                            </DialogDescription>
                        </DialogHeader>

                        <div className="flex-1 overflow-y-auto pr-2 space-y-6 custom-scrollbar">
                            <div className="space-y-3">
                                <div className="flex items-center justify-between">
                                    <Label className="text-sm font-medium text-slate-200">选择用例 (Select Test Cases)</Label>
                                    <Button variant="ghost" size="sm" onClick={selectAllTcs} className="text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 h-7 text-xs px-2">
                                        {tcData?.items && selectedTcIds.length === tcData.items.length ? "取消全选 (Deselect All)" : "全选全部 (Select All)"}
                                    </Button>
                                </div>
                                <div className="border border-slate-800 rounded-lg bg-slate-950 p-2 h-[240px] overflow-y-auto mb-2 custom-scrollbar">
                                    {(!tcData?.items || tcData.items.length === 0) ? (
                                        <div className="text-center text-slate-500 py-10 text-sm">暂无存量测试用例 (No test cases found)</div>
                                    ) : (
                                        tcData.items.map((tc: any) => (
                                            <div key={tc.id} className="flex items-center gap-3 p-2.5 hover:bg-slate-800/50 rounded-md transition-colors cursor-pointer group" onClick={() => toggleTcSelection(tc.id)}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedTcIds.includes(tc.id)}
                                                    onChange={() => { }}
                                                    className="w-4 h-4 rounded bg-slate-900 border-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-950 cursor-pointer pointer-events-none"
                                                />
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs font-mono text-slate-400">{tc.id}</span>
                                                        <span className="text-sm text-slate-200 font-medium truncate group-hover:text-blue-200 transition-colors">{tc.name}</span>
                                                    </div>
                                                </div>
                                                {tc.mode === 'UI' ? (
                                                    <Badge className="bg-purple-500/10 text-purple-400 border-purple-500/20 text-[10px] px-1.5 py-0">UI</Badge>
                                                ) : tc.mode === 'API' ? (
                                                    <Badge className="bg-green-500/10 text-green-400 border-green-500/20 text-[10px] px-1.5 py-0">API</Badge>
                                                ) : (
                                                    <Badge className="bg-blue-500/10 text-blue-400 border-blue-500/20 text-[10px] px-1.5 py-0">HYBRID</Badge>
                                                )}
                                            </div>
                                        ))
                                    )}
                                </div>
                                <div className="text-xs text-slate-500 text-right">已选择: {selectedTcIds.length}个用例 (Selected: {selectedTcIds.length} cases)</div>
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label className="text-slate-300">执行模式 (Execution Mode)</Label>
                                    <Select value={mode} onValueChange={setMode}>
                                        <SelectTrigger className="bg-slate-900 border-slate-700 h-9">
                                            <SelectValue placeholder="Select mode" />
                                        </SelectTrigger>
                                        <SelectContent className="bg-slate-900 border-slate-700">
                                            <SelectItem value="normal" className="focus:bg-slate-800">普通执行 (Normal Execution)</SelectItem>
                                            <SelectItem value="debug" className="focus:bg-slate-800">调试执行 (Debug Execution)</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="space-y-2">
                                    <Label className="text-slate-300">环境 (Environment)</Label>
                                    <Input value={env} onChange={e => setEnv(e.target.value)} className="bg-slate-900 border-slate-700 h-9 text-slate-200" placeholder="dev, staging, prod..." />
                                </div>
                            </div>

                            <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-800/50">
                                <div className="space-y-0.5">
                                    <Label className="text-slate-200 text-sm">并行执行 (Parallel Execution)</Label>
                                    <p className="text-xs text-slate-500">启用Celery并发，加速长列表测试 (Enable Celery concurrency to accelerate tests)</p>
                                </div>
                                <Switch checked={parallel} onCheckedChange={setParallel} className="data-[state=checked]:bg-blue-500" />
                            </div>
                        </div>

                        <DialogFooter className="mt-6 border-t border-slate-800 pt-4 flex-shrink-0">
                            <Button variant="outline" onClick={() => setIsDialogOpen(false)} className="border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800">
                                取消 (Cancel)
                            </Button>
                            <Button onClick={handleStart} disabled={mutation.isPending || selectedTcIds.length === 0} className="bg-blue-600 hover:bg-blue-700 text-white min-w-[120px]">
                                {mutation.isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
                                执行回归 (Run Regression)
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            {/* Metrics Header */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <Card className="bg-slate-900 border-slate-800 shadow-lg shadow-black/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400">执行总数 (Total Executions)</CardTitle>
                        <Activity className="h-4 w-4 text-slate-500" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-100">{statsData?.total || 0}</div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800 shadow-lg shadow-black/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400">运行中任务 (Active Tasks)</CardTitle>
                        <RefreshCw className={`h-4 w-4 text-blue-400 ${statsData?.active > 0 ? 'animate-spin' : ''}`} />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-100">{statsData?.active || 0}</div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800 shadow-lg shadow-black/20 relative overflow-hidden">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-green-500/5 rounded-full blur-3xl -mr-10 -mt-10 pointer-events-none" />
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400">成功率 (Success Rate)</CardTitle>
                        <Activity className="h-4 w-4 text-green-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-100 flex items-baseline gap-1">
                            {statsData?.success_rate || 0}
                            <span className="text-base text-slate-500">%</span>
                        </div>
                    </CardContent>
                </Card>
                <Card className="bg-slate-900 border-slate-800 shadow-lg shadow-black/20">
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium text-slate-400">平均耗时 (Avg Duration)</CardTitle>
                        <Loader2 className="h-4 w-4 text-purple-400" />
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-100 flex items-baseline gap-1">
                            {statsData?.avg_duration || 0}
                            <span className="text-base text-slate-500">s</span>
                        </div>
                    </CardContent>
                </Card>
            </div>

            <Card className="bg-slate-900 border-slate-800">
                {/* ... existing card header ... */}
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow className="border-slate-800 hover:bg-transparent">
                                <TableHead className="text-slate-200">执行ID (Execution ID)</TableHead>
                                <TableHead className="text-slate-200">状态 (Status)</TableHead>
                                <TableHead className="text-slate-200">进度 (Progress)</TableHead>
                                <TableHead className="text-slate-200 text-right">通过 / 失败 (Pass / Fail)</TableHead>
                                <TableHead className="text-slate-200 text-right">耗时 (Elapsed)</TableHead>
                                <TableHead className="text-slate-200 text-right w-[80px]">操作 (Actions)</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {executions?.map((exec) => (
                                <TableRow
                                    key={exec.execution_id}
                                    className="border-slate-800 hover:bg-slate-800/50 cursor-pointer transition-colors"
                                    onClick={() => handleRowClick(exec.execution_id)}
                                >
                                    <TableCell className="font-mono text-xs text-slate-200">{exec.execution_id}</TableCell>
                                    <TableCell>
                                        <StatusBadge status={exec.status} />
                                    </TableCell>
                                    <TableCell className="w-[200px]">
                                        <div className="flex items-center gap-3">
                                            <div className="relative w-full h-2 bg-slate-800 rounded-full overflow-hidden shrink-0">
                                                <div
                                                    className={`absolute top-0 left-0 h-full rounded-full transition-all duration-500 ${exec.status.toLowerCase() === 'running' ? 'bg-gradient-to-r from-blue-500 via-indigo-400 to-blue-500 bg-[length:200%_100%] animate-pulse' : exec.status.toLowerCase() === 'failed' ? 'bg-red-500' : 'bg-green-500'}`}
                                                    style={{ width: `${Math.round(exec.progress)}%` }}
                                                />
                                            </div>
                                            <span className="text-xs text-slate-300 w-10 text-right font-mono">{Math.round(exec.progress)}%</span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <span className="text-green-400 font-medium">{exec.passed}</span>
                                        <span className="text-slate-400 mx-1">/</span>
                                        <span className="text-red-400 font-medium">{exec.failed}</span>
                                    </TableCell>
                                    <TableCell className="text-right text-slate-200 font-mono">
                                        {exec.elapsed_seconds.toFixed(1)}s
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8 text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
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
                    <div className="flex items-center justify-between pt-4 border-t border-slate-800/50 mt-4">
                        <p className="text-sm text-slate-400">
                            Showing <span className="font-medium text-slate-200">{executions.length}</span> of{" "}
                            <span className="font-medium text-slate-200">{total}</span> executions
                        </p>
                        <div className="flex items-center space-x-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                                disabled={currentPage === 1}
                                className="border-slate-700 bg-slate-900/50 text-slate-300 hover:bg-slate-800 hover:text-slate-100 h-8"
                            >
                                上一页 (Previous)
                            </Button>
                            <span className="text-sm text-slate-400 min-w-[3rem] text-center font-mono">
                                {currentPage} / {totalPages}
                            </span>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                                disabled={currentPage === totalPages}
                                className="border-slate-700 bg-slate-900/50 text-slate-300 hover:bg-slate-800 hover:text-slate-100 h-8"
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
                <DialogContent className="bg-slate-900 border-slate-800 text-slate-200">
                    <DialogHeader>
                        <DialogTitle>删除执行记录 (Delete Execution Record)</DialogTitle>
                        <DialogDescription className="text-slate-400">
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

