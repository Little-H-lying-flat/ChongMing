"use client";

import React, { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Globe, Info, Plus, Pencil, Trash2, HeartPulse, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
    getEnvironments, createEnvironment, updateEnvironment, deleteEnvironment,
    checkEnvironmentHealth, Environment
} from "@/services/environmentService";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import Link from "next/link";

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState("environments");

    // ================= 环境管理 State =================
    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [loadingEnvs, setLoadingEnvs] = useState(true);

    // 环境 Dialog
    const [envDialogOpen, setEnvDialogOpen] = useState(false);
    const [editingEnv, setEditingEnv] = useState<Partial<Environment> | null>(null);
    const [savingEnv, setSavingEnv] = useState(false);

    // ================= 初始加载 =================
    useEffect(() => {
        fetchEnvironments();
    }, []);

    const fetchEnvironments = async () => {
        setLoadingEnvs(true);
        try {
            // 获取所有环境 (包含非 active 的)
            const data = await getEnvironments(false);
            setEnvironments(data);
        } catch (_error) {
            toast.error("加载环境列表失败 (Failed to load environments)");
        } finally {
            setLoadingEnvs(false);
        }
    };

    // ================= 环境管理逻辑 =================
    const handleAddEnvironment = () => {
        setEditingEnv({ name: "", base_url: "", description: "", is_active: true });
        setEnvDialogOpen(true);
    };

    const handleEditEnvironment = (env: Environment) => {
        setEditingEnv({ ...env });
        setEnvDialogOpen(true);
    };

    const handleDeleteEnvironment = async (id: string, name: string) => {
        if (!confirm(`确定要删除环境"${name}"吗？此操作不可逆。 (Delete environment "${name}"? This is irreversible.)`)) return;
        try {
            await deleteEnvironment(id);
            toast.success(`环境"${name}"已删除 (Environment "${name}" deleted)`);
            fetchEnvironments();
        } catch (_error) {
            toast.error("删除失败 (Delete Failed)");
        }
    };

    const handleCheckHealth = async (id: string) => {
        toast.loading("检测健康状态中... (Checking health...)", { id: `health-${id}` });
        try {
            const res = await checkEnvironmentHealth(id);
            if (res.overall_status === "healthy") {
                toast.success(`[${res.environment_name}] 状态健康 (Healthy)`, { id: `health-${id}` });
            } else {
                toast.warning(`[${res.environment_name}] 异常: 详情请见控制台 (Abnormal: See console)`, { id: `health-${id}` });
            }
        } catch (_error) {
            toast.error("健康检测失败，目标环境可能不可达 (Health check failed, target may be unreachable)", { id: `health-${id}` });
        }
    };

    const saveEnvironment = async () => {
        if (!editingEnv?.name || !editingEnv?.base_url) {
            toast.error("请输入名称和Base URL (Please enter Name and Base URL)");
            return;
        }

        setSavingEnv(true);
        try {
            if (editingEnv.id) {
                await updateEnvironment(editingEnv.id, editingEnv);
                toast.success("环境更新成功 (Environment Updated)");
            } else {
                await createEnvironment(editingEnv as Parameters<typeof createEnvironment>[0]);
                toast.success("环境创建成功 (Environment Created)");
            }
            setEnvDialogOpen(false);
            fetchEnvironments();
        } catch (error: unknown) {
            const err = error as { response?: { data?: { detail?: string } } };
            toast.error(err.response?.data?.detail || "保存失败 (Save Failed)");
        } finally {
            setSavingEnv(false);
        }
    };

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-slate-950 mb-1">系统配置中心 (System Configuration Center)</h1>
                    <p className="text-slate-600">管理运行环境与基础配置 (Manage runtime environments and basic configuration)</p>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-white/80 border border-sky-100">
                    <TabsTrigger value="environments" className="data-[state=active]:bg-sky-50 text-slate-700 data-[state=active]:text-slate-950">
                        <Globe className="w-4 h-4 mr-2" /> 环境管理 (Environments)
                    </TabsTrigger>
                    <TabsTrigger value="about" className="data-[state=active]:bg-sky-50 text-slate-700 data-[state=active]:text-slate-950">
                        <Info className="w-4 h-4 mr-2" /> 平台信息 (Platform Info)
                    </TabsTrigger>
                </TabsList>

                {/* =================环境管理 TAB================= */}
                <TabsContent value="environments" className="space-y-4">
                    <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-xl text-slate-900 font-bold">运行环境矩阵 (Runtime Environment Matrix)</CardTitle>
                                <CardDescription className="text-slate-600 mt-1">设置平台自动化执行的目标网关与全局注入变量 (Configure target gateways and global injection variables)</CardDescription>
                            </div>
                            <Button onClick={handleAddEnvironment} className="bg-gradient-to-r from-violet-500 to-fuchsia-500 text-white shadow-lg shadow-violet-500/25 hover:from-violet-600 hover:to-fuchsia-600">
                                <Plus className="w-4 h-4 mr-1" /> 新建环境 (New Environment)
                            </Button>
                        </CardHeader>
                        <CardContent>
                            {loadingEnvs ? (
                                <div className="space-y-3">
                                    <Skeleton className="h-10 w-full bg-sky-50" />
                                    <Skeleton className="h-10 w-full bg-sky-50" />
                                    <Skeleton className="h-10 w-full bg-sky-50" />
                                </div>
                            ) : (
                                <div className="rounded-md border border-sky-100 overflow-hidden">
                                    <Table>
                                        <TableHeader className="bg-white/80">
                                            <TableRow className="border-sky-100 hover:bg-transparent">
                                                <TableHead className="text-slate-700">环境名称 (Name)</TableHead>
                                                <TableHead className="text-slate-700">Base URL</TableHead>
                                                <TableHead className="text-slate-700">变量 (Variables)</TableHead>
                                                <TableHead className="text-slate-700">状态 (Status)</TableHead>
                                                <TableHead className="text-right text-slate-700">操作 (Actions)</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {environments.length === 0 ? (
                                                <TableRow className="border-sky-100">
                                                    <TableCell colSpan={5} className="text-center py-6 text-slate-500">
                                                        暂未配置任何环境 (No environments configured)
                                                    </TableCell>
                                                </TableRow>
                                            ) : environments.map((env) => (
                                                <TableRow key={env.id} className="border-sky-100 border-t hover:bg-sky-50/50">
                                                    <TableCell className="font-medium flex items-center gap-2 text-slate-800">
                                                        {env.name}
                                                        {env.is_default && <Badge variant="secondary" className="bg-sky-50 text-sky-700 font-normal border-sky-200">默认 (Default)</Badge>}
                                                    </TableCell>
                                                    <TableCell className="text-slate-800 font-mono text-xs">{env.base_url}</TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="border-sky-200 text-slate-600">
                                                            {Object.keys(env.variables || {}).length} vars (个)
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>
                                                        {env.is_active ?
                                                            <div className="flex items-center text-emerald-400 text-xs gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> 已启用 (Enabled)</div> :
                                                            <div className="flex items-center text-slate-500 text-xs gap-1.5"><div className="w-1.5 h-1.5 rounded-full bg-slate-500" /> 已停用 (Disabled)</div>
                                                        }
                                                    </TableCell>
                                                    <TableCell className="text-right space-x-2">
                                                        <Button variant="ghost" size="sm" onClick={() => handleCheckHealth(env.id!)} className="h-8 shadow-none text-slate-600 hover:text-sky-700 hover:bg-sky-50" title="健康检测 (Health Check)">
                                                            <HeartPulse className="w-4 h-4" />
                                                        </Button>
                                                        <Button variant="ghost" size="sm" onClick={() => handleEditEnvironment(env)} className="h-8 px-2 text-slate-600 hover:text-slate-950" title="编辑 (Edit)">
                                                            <Pencil className="w-4 h-4" />
                                                        </Button>
                                                        <Button variant="ghost" size="sm" onClick={() => handleDeleteEnvironment(env.id!, env.name)} className="h-8 px-2 text-slate-500 hover:text-rose-700 hover:bg-rose-50" title="删除 (Delete)">
                                                            <Trash2 className="w-4 h-4" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="rounded-2xl border-violet-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(139,92,246,0.3)] backdrop-blur-xl">
                        <CardHeader className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                            <div>
                                <CardTitle className="text-lg text-slate-900 font-bold">AI 模型与 Provider 配置已收敛到模型治理</CardTitle>
                                <CardDescription className="text-slate-600 mt-1">
                                    系统设置只保留运行环境等基础配置；API Key、Base URL 和模型路由请统一在模型治理页面维护。
                                </CardDescription>
                            </div>
                            <Button asChild variant="outline" className="border-violet-200 bg-white text-violet-700 hover:bg-violet-50 hover:text-violet-800">
                                <Link href="/model-config">前往模型治理</Link>
                            </Button>
                        </CardHeader>
                    </Card>
                </TabsContent>

                {/* =================平台信息 TAB================= */}
                <TabsContent value="about" className="space-y-4">
                    <Card className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl overflow-hidden">
                        <div className="h-2 bg-gradient-to-r from-blue-600 to-cyan-400 w-full" />
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-2xl font-black bg-gradient-to-br from-white to-slate-400 bg-clip-text text-transparent">
                                ChongMing
                                <Badge className="bg-sky-600 hover:bg-sky-600 text-white rounded-full font-mono font-medium ml-2">v0.1.1</Badge>
                            </CardTitle>
                            <CardDescription className="text-slate-600">重明智能测试引擎 (Agentic Testing Platform)</CardDescription>
                        </CardHeader>
                        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
                            <div className="space-y-4">
                                <div>
                                    <h4 className="text-sm font-semibold text-slate-700 mb-2">系统架构 (System Architecture)</h4>
                                    <div className="space-y-2">
                                        <div className="flex justify-between text-sm py-1 border-b border-sky-100/50">
                                            <span className="text-slate-500">网关前端 (Frontend Gateway)</span>
                                            <span className="text-slate-700 font-mono">Next.js 16 + React 18</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-sky-100/50">
                                            <span className="text-slate-500">主控中枢 (Backend Core)</span>
                                            <span className="text-slate-700 font-mono">Python 3.12 + FastAPI</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-sky-100/50">
                                            <span className="text-slate-500">数据持久层 (Data Persistence)</span>
                                            <span className="text-slate-700 font-mono">PostgreSQL (SQLAlchemy 2.0)</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-sky-100/50">
                                            <span className="text-slate-500">任务网格 (Task Grid)</span>
                                            <span className="text-slate-700 font-mono">Redis + Celery Worker</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-sky-100/50">
                                            <span className="text-slate-500">向量检索</span>
                                            <span className="text-slate-700 font-mono">Chroma / Milvus</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-white p-5 rounded-lg border border-sky-100">
                                <h4 className="flex items-center gap-2 text-sm font-semibold text-emerald-400 mb-3">
                                    <ShieldAlert className="w-4 h-4" /> 架构与安全声明
                                </h4>
                                <p className="text-sm text-slate-600 leading-relaxed">
                                    重明平台采用去中心化可插拔微生架构。所有配置和敏感令牌在入表前由内置密钥进行封壳加密。环境变量支持严格的数据隔离。
                                    当前节点运行模式为 <span className="font-mono text-sky-700">Development</span>。
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* =================弹窗: 环境编辑================= */}
            <Dialog open={envDialogOpen} onOpenChange={setEnvDialogOpen}>
                <DialogContent className="rounded-2xl border-sky-100 bg-white/80 text-slate-950 max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{editingEnv?.id ? "编辑环境 (Edit Environment)" : "新建环境配置 (New Environment Configuration)"}</DialogTitle>
                        <DialogDescription className="text-slate-600">
                            配置此环境网关对应的根 URL 以及全局自动注入的变量字典 (Configure the base URL and global variables for this environment gateway)
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="name">环境标识名称 (Environment Name) <span className="text-red-500">*</span></Label>
                                <Input
                                    id="name"
                                    value={editingEnv?.name || ''}
                                    onChange={(e) => setEditingEnv({ ...editingEnv, name: e.target.value })}
                                    placeholder="e.g. 预发环境 Staging"
                                    className="bg-white border-sky-100"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="base_url">Gateway Base URL <span className="text-red-500">*</span></Label>
                                <Input
                                    id="base_url"
                                    value={editingEnv?.base_url || ''}
                                    onChange={(e) => setEditingEnv({ ...editingEnv, base_url: e.target.value })}
                                    placeholder="https://api.staging.example.com"
                                    className="bg-white border-sky-100 font-mono text-sm"
                                />
                            </div>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="desc">描述信息 (Description)</Label>
                            <Input
                                id="desc"
                                value={editingEnv?.description || ''}
                                onChange={(e) => setEditingEnv({ ...editingEnv, description: e.target.value })}
                                placeholder="选填，关于该环境的补充说明 (Optional description)"
                                className="bg-white border-sky-100 text-sm"
                            />
                        </div>

                        <div className="flex items-center gap-4 pt-2">
                            <div className="flex items-center gap-2">
                                <Switch
                                    id="active"
                                    checked={editingEnv?.is_active ?? true}
                                    onCheckedChange={(c) => setEditingEnv({ ...editingEnv, is_active: c })}
                                />
                                <Label htmlFor="active" className="cursor-pointer">启用此环境 (Enable this environment)</Label>
                            </div>
                            {/* For simplicity we didn't add the full key-value array editor inside here for MVP, keep as is */}
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setEnvDialogOpen(false)} className="border-sky-200 bg-transparent text-slate-700">取消 (Cancel)</Button>
                        <Button onClick={saveEnvironment} disabled={savingEnv} className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600">
                            {savingEnv ? "保存中... (Saving...)" : "保存配置 (Save Configuration)"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

        </div>
    );
}
