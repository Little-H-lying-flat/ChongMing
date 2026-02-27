"use client"

import React, { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2, Code2, Save, PlayCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { format } from "date-fns";

import { apiAutoService, ApiTestCase, ApiStep, ChainExecutionResult } from '@/services/apiAutoService';
import { RequestBuilder } from '@/components/api-auto/RequestBuilder';
import { ResponseConsole } from '@/components/api-auto/ResponseConsole';
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { getEnvironments, Environment } from '@/services/environmentService';

const NEW_STEP_TEMPLATE: ApiStep = {
    id: "step_1",
    name: "Request 1",
    request: {
        method: "GET",
        url: "https://jsonplaceholder.typicode.com/todos/1",
        headers: {
            "Accept": "application/json"
        },
        query_params: {},
        timeout_ms: 10000
    },
    extraction: {},
    assertion: {
        status_code: 200,
        json_assertions: {}
    }
};

export default function ApiAutoPage() {
    const [cases, setCases] = useState<ApiTestCase[]>([]);
    const [activeCase, setActiveCase] = useState<ApiTestCase | null>(null);
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isExecuting, setIsExecuting] = useState(false);

    // Console State
    const [execResult, setExecResult] = useState<ChainExecutionResult | null>(null);

    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [caseToDelete, setCaseToDelete] = useState<string | null>(null);

    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [selectedEnv, setSelectedEnv] = useState<string>("default");

    useEffect(() => {
        loadCases();
        loadEnvironments();
    }, []);

    const loadEnvironments = async () => {
        try {
            const data = await getEnvironments(true);
            setEnvironments(data);
        } catch (err) {
            console.error("Failed to load environments", err);
        }
    };

    const loadCases = async () => {
        setIsLoadingList(true);
        try {
            const res = await apiAutoService.getCases();
            setCases(res.data.items || []);
            // Pre-select first item if exists and no active case
            if (res.data.items?.length > 0 && !activeCase) {
                setActiveCase(res.data.items[0]);
            }
        } catch (err: any) {
            if (!err?.message?.includes("Failed to fetch")) {
                toast.error("加载接口用例失败 (Failed to load API cases)", { description: err.message });
            }
        } finally {
            setIsLoadingList(false);
        }
    };

    const handleCreateNew = () => {
        const newCase: ApiTestCase = {
            id: "NEW", // Marker for unsaved
            name: "未命名接口集合 (Untitled API Collection)",
            description: "",
            mode: "API",
            priority: "P1",
            status: "active",
            tags: [],
            steps: [{ ...NEW_STEP_TEMPLATE }] // Deep copy to prevent ref sharing if created multiple times
        };
        setActiveCase(newCase);
        setExecResult(null); // Clear console
    };

    const handleSave = async () => {
        if (!activeCase) return;
        setIsSaving(true);
        try {
            let savedCase;
            if (activeCase.id === "NEW") {
                const { id, ...payload } = activeCase;
                const res = await apiAutoService.createCase(payload);
                savedCase = res.data;
                toast.success("新建成功 (Created)");
            } else {
                const res = await apiAutoService.updateCase(activeCase.id!, activeCase);
                savedCase = res.data;
                toast.success("保存成功 (Saved)");
            }
            setActiveCase(savedCase);
            await loadCases();
        } catch (err: any) {
            toast.error("保存失败 (Save Failed)", { description: err.message });
        } finally {
            setIsSaving(false);
        }
    };

    const handleDeleteClick = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setCaseToDelete(id);
        setDeleteConfirmOpen(true);
    };

    const confirmDelete = async () => {
        if (!caseToDelete) return;
        try {
            await apiAutoService.deleteCase(caseToDelete);
            toast.success("已删除 (Deleted)");
            if (activeCase?.id === caseToDelete) setActiveCase(null);
            loadCases();
        } catch (err: any) {
            toast.error("删除失败 (Delete Failed)", { description: err.message });
        } finally {
            setDeleteConfirmOpen(false);
            setCaseToDelete(null);
        }
    };

    const handleRunChain = async () => {
        if (!activeCase || activeCase.steps.length === 0) {
            toast.error("没有可执行的请求 (No executable requests)");
            return;
        }

        setIsExecuting(true);
        setExecResult(null);

        try {
            const envId = selectedEnv === "default" ? undefined : selectedEnv;
            const res = await apiAutoService.runApiChain(activeCase.steps, "", {}, {}, envId);
            setExecResult(res.data);
            if (res.data.success) {
                toast.success("执行完成: 全通过 (Execution Complete: All Passed)");
            } else {
                toast.error(`执行完成: ${res.data.failed_steps}个失败 (Execution Complete: ${res.data.failed_steps} Failed)`);
            }
        } catch (err: any) {
            toast.error("执行接口失败 (API Execution Failed)", { description: err.message });
        } finally {
            setIsExecuting(false);
        }
    };

    const updateActiveCaseField = (field: keyof ApiTestCase, value: any) => {
        if (!activeCase) return;
        setActiveCase({ ...activeCase, [field]: value });
    };

    const updateStep = (index: number, newStep: ApiStep) => {
        if (!activeCase) return;
        const newSteps = [...activeCase.steps];
        newSteps[index] = newStep;
        setActiveCase({ ...activeCase, steps: newSteps });
    };

    return (
        <div className="flex-1 flex overflow-hidden min-h-screen bg-slate-950 text-slate-200">
            {/* Left Panel: API Case Library */}
            <div className="w-80 border-r border-slate-800 bg-slate-900 flex flex-col h-full shrink-0">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                    <h2 className="font-semibold flex items-center gap-2 text-slate-200">
                        <Code2 className="h-5 w-5 text-indigo-500" />
                        API接口工厂 (API Factory)
                    </h2>
                    <Button size="icon" variant="ghost" onClick={handleCreateNew}>
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {isLoadingList ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">加载中... (Loading...)</p>
                    ) : cases.length === 0 ? (
                        <p className="p-4 text-center text-sm text-muted-foreground">空空如也，快去创建吧 (Empty, create one!)</p>
                    ) : (
                        cases.map(tc => (
                            <div
                                key={tc.id}
                                onClick={() => { setActiveCase(tc); setExecResult(null); }}
                                className={`p-3 rounded-md cursor-pointer border transition-colors group ${activeCase?.id === tc.id ? 'border-indigo-500 bg-indigo-500/10 text-slate-200' : 'border-transparent bg-transparent hover:bg-slate-800/50 text-slate-300'}`}
                            >
                                <div className="flex justify-between items-start">
                                    <div className="truncate font-medium text-sm">{tc.name}</div>
                                    <Trash2 className="h-4 w-4 text-rose-400 opacity-0 group-hover:opacity-100 transition-opacity hover:text-rose-500" onClick={(e) => handleDeleteClick(tc.id!, e)} />
                                </div>
                                <div className="text-xs text-slate-500 mt-1 flex justify-between">
                                    <span>{tc.steps?.length || 0} Req</span>
                                    <span>{tc.updated_at ? format(new Date(tc.updated_at), 'MM-dd HH:mm') : 'New'}</span>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>

            {/* Right Panel: API Workbench */}
            <div className="flex-1 flex flex-col h-full bg-[#0d1117] overflow-y-auto">
                {activeCase ? (
                    <div className="p-6 max-w-6xl w-full mx-auto space-y-6">
                        {/* Workbench Header */}
                        <div className="flex items-center justify-between">
                            <div className="flex-1 max-w-xl">
                                <Input
                                    className="text-2xl font-bold bg-transparent border-0 border-b border-transparent focus-visible:ring-0 focus-visible:border-indigo-500 h-10 px-0 shadow-none rounded-none text-slate-100"
                                    value={activeCase.name}
                                    onChange={(e) => updateActiveCaseField("name", e.target.value)}
                                    placeholder="集合名称 (Collection Name)"
                                />
                                <Input
                                    className="text-sm text-slate-400 bg-transparent border-0 h-7 px-0 shadow-none focus-visible:ring-0 mt-1"
                                    value={activeCase.description || ""}
                                    onChange={(e) => updateActiveCaseField("description", e.target.value)}
                                    placeholder="添加关于此集合的业务描述... (Add business description...)"
                                />
                            </div>
                            <div className="flex items-center gap-3">
                                <Select value={selectedEnv} onValueChange={setSelectedEnv}>
                                    <SelectTrigger className="w-48 bg-slate-900 border-slate-700 text-slate-200 h-9 text-sm">
                                        <SelectValue placeholder="选择运行环境" />
                                    </SelectTrigger>
                                    <SelectContent className="bg-slate-900 border-slate-700 text-slate-200">
                                        <SelectItem value="default">无环境设定 (No Env)</SelectItem>
                                        {environments.map(env => (
                                            <SelectItem key={env.id} value={env.id}>
                                                {env.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>

                                <Button variant="outline" size="sm" onClick={handleSave} disabled={isSaving} className="border-slate-700 bg-slate-900 text-slate-300 hover:bg-slate-800 hover:text-slate-100">
                                    <Save className="h-4 w-4 mr-2" />
                                    {isSaving ? "保存中" : "保存"}
                                </Button>
                                {/* Only allow chain execution if we have steps */}
                                {activeCase.steps.length > 0 && (
                                    <Button size="sm" onClick={handleRunChain} disabled={isExecuting} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                                        <PlayCircle className="h-4 w-4 mr-2" />
                                        运行 ({activeCase.steps.length})
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Request Map (For MVP, just show the first step as the main request builder. 
                            In a full Postman, we'd have a sidebar inside the workbench to select steps. 
                            Let's map through steps for now sequentially as cards) */}
                        <div className="space-y-8">
                            {activeCase.steps.map((step, index) => (
                                <div key={index} className="space-y-2">
                                    <div className="flex items-center justify-between px-1">
                                        <h3 className="font-semibold text-slate-300 flex items-center gap-2">
                                            <span className="bg-slate-800 text-slate-400 text-xs px-2 py-0.5 rounded">步骤 (Step) {index + 1}</span>
                                            {step.name}
                                        </h3>
                                    </div>
                                    {((step as any).step_type === "UI" || !step.request) ? (
                                        <div className="p-4 bg-slate-900/50 rounded-md border border-slate-800 text-slate-400 flex flex-col gap-2">
                                            <div className="flex items-center text-amber-500 text-sm">
                                                <AlertCircle className="w-4 h-4 mr-2" />
                                                包含了非 API 类型的步骤 (UI/混合步骤)
                                            </div>
                                            <div className="text-sm">
                                                描述 (Description): {(step as any).description || "无"}
                                            </div>
                                            <div className="text-sm">
                                                目前 API 工作台仅支持可视化编排 HTTP 接口测试步骤。
                                            </div>
                                        </div>
                                    ) : (
                                        <RequestBuilder
                                            step={step}
                                            onChange={(newStep) => updateStep(index, newStep)}
                                            onRun={handleRunChain}
                                            isExecuting={isExecuting}
                                        />
                                    )}
                                </div>
                            ))}
                        </div>

                        {/* Console Panel */}
                        <ResponseConsole result={execResult} isLoading={isExecuting} />

                    </div>
                ) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground">
                        <Code2 className="h-16 w-16 mb-4 text-slate-700 opacity-50" />
                        <p className="text-lg">选择左侧用例，进入API自动化工作区 (Select a case to enter the API workbench)</p>
                    </div>
                )}
            </div>

            <AlertDialog open={deleteConfirmOpen} onOpenChange={setDeleteConfirmOpen}>
                <AlertDialogContent className="bg-slate-900 border-slate-800 text-slate-200">
                    <AlertDialogHeader>
                        <AlertDialogTitle>确定删除此API用例吗？ (Delete this API case?)</AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-400">
                            此操作不可逆，将永久删除。 (This action is irreversible and permanent.)
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700 hover:text-slate-200">取消 (Cancel)</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} className="bg-rose-600 hover:bg-rose-700 text-white border-none">
                            确定删除 (Confirm Delete)
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
