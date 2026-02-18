"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Loader2, RefreshCw, Play, Activity } from "lucide-react";
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
const fetchExecutions = async (): Promise<ExecutionStatus[]> => {
    const res = await fetch("/api/v1/executions?limit=20");
    if (!res.ok) throw new Error("Failed to fetch executions");
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

    // Form State
    const [tcIdsInput, setTcIdsInput] = useState("TC-001\nTC-002");
    const [mode, setMode] = useState("normal");
    const [parallel, setParallel] = useState(true);
    const [maxWorkers, setMaxWorkers] = useState(5);
    const [env, setEnv] = useState("dev");

    // Query
    const { data: executions, isLoading, isError } = useQuery({
        queryKey: ["executions"],
        queryFn: fetchExecutions,
        refetchInterval: 2000, // Poll every 2s
    });

    // Mutation
    const mutation = useMutation({
        mutationFn: startExecution,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["executions"] });
            setIsDialogOpen(false);
        },
    });

    const handleStart = () => {
        const tc_ids = tcIdsInput.split("\n").map(id => id.trim()).filter(id => id);
        mutation.mutate({
            tc_ids,
            mode,
            parallel,
            max_workers: Number(maxWorkers),
            env,
        });
    };

    const StatusBadge = ({ status }: { status: string }) => {
        const s = status.toLowerCase();
        let className = "";
        if (s === "passed") className = "bg-green-500 hover:bg-green-600 border-transparent";
        else if (s === "failed") className = "bg-red-500 hover:bg-red-600 border-transparent";
        else if (s === "running") className = "bg-blue-500 hover:bg-blue-600 border-transparent animate-pulse";
        else if (s === "pending") className = "bg-yellow-500 hover:bg-yellow-600 border-transparent text-slate-900";
        else className = "bg-slate-500 hover:bg-slate-600 border-transparent";

        return <Badge className={className}>{status}</Badge>;
    };

    const handleRowClick = (executionId: string) => {
        setSelectedExecutionId(executionId);
    };

    // ... existing render ...

    return (
        <div className="space-y-6">

            {/* ... existing header ... */}

            <Card className="bg-slate-900 border-slate-800">
                {/* ... existing card header ... */}
                <CardContent>
                    <Table>
                        <TableHeader>
                            <TableRow className="border-slate-800 hover:bg-transparent">
                                <TableHead className="text-slate-200">Execution ID</TableHead>
                                <TableHead className="text-slate-200">Status</TableHead>
                                <TableHead className="text-slate-200">Progress</TableHead>
                                <TableHead className="text-slate-200 text-right">Pass / Fail</TableHead>
                                <TableHead className="text-slate-200 text-right">Elapsed</TableHead>
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
                                        <div className="flex items-center gap-2">
                                            <Progress value={exec.progress} className="h-2 bg-slate-700" />
                                            <span className="text-xs text-slate-300 w-8 text-right">{Math.round(exec.progress)}%</span>
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
                                </TableRow>
                            ))}
                            {/* ... empty state ... */}
                        </TableBody>
                    </Table>
                </CardContent>
            </Card>

            <ExecutionDrawer
                executionId={selectedExecutionId}
                open={!!selectedExecutionId}
                onClose={() => setSelectedExecutionId(null)}
            />
        </div>
    );
}

