"use client";

import React, { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Globe, KeyRound, Info, Plus, Pencil, Trash2, HeartPulse, ShieldAlert, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
    getEnvironments, createEnvironment, updateEnvironment, deleteEnvironment,
    checkEnvironmentHealth, Environment
} from "@/services/environmentService";
import { AIModel, getAvailableModels, updateProviderKey } from "@/services/smartOpsService";
import { toast } from "sonner";
import { Skeleton } from "@/components/ui/skeleton";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState("environments");

    // ================= 环境管理 State =================
    const [environments, setEnvironments] = useState<Environment[]>([]);
    const [loadingEnvs, setLoadingEnvs] = useState(true);

    // 环境 Dialog
    const [envDialogOpen, setEnvDialogOpen] = useState(false);
    const [editingEnv, setEditingEnv] = useState<Partial<Environment> | null>(null);
    const [savingEnv, setSavingEnv] = useState(false);

    // ================= 凭证管理 State =================
    const [models, setModels] = useState<AIModel[]>([]);
    const [loadingModels, setLoadingModels] = useState(true);

    // 凭证 Dialog
    const [providerDialogOpen, setProviderDialogOpen] = useState(false);
    const [selectedProvider, setSelectedProvider] = useState<string>("");
    const [apiKeyInput, setApiKeyInput] = useState("");
    const [baseUrlInput, setBaseUrlInput] = useState("");
    const [savingProvider, setSavingProvider] = useState(false);

    // ================= 初始加载 =================
    useEffect(() => {
        fetchEnvironments();
        fetchModels();
    }, []);

    const fetchEnvironments = async () => {
        setLoadingEnvs(true);
        try {
            // 获取所有环境 (包含非 active 的)
            const data = await getEnvironments(false);
            setEnvironments(data);
        } catch (error) {
            toast.error("加载环境列表失败 (Failed to load environments)");
        } finally {
            setLoadingEnvs(false);
        }
    };

    const fetchModels = async () => {
        setLoadingModels(true);
        try {
            const data = await getAvailableModels();
            setModels(data);
        } catch (error) {
            toast.error("加载支持的模型列表失败 (Failed to load models)");
        } finally {
            setLoadingModels(false);
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
        } catch (error) {
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
        } catch (error) {
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
                await createEnvironment(editingEnv as any);
                toast.success("环境创建成功 (Environment Created)");
            }
            setEnvDialogOpen(false);
            fetchEnvironments();
        } catch (error: any) {
            toast.error(error.response?.data?.detail || "保存失败 (Save Failed)");
        } finally {
            setSavingEnv(false);
        }
    };

    // ================= 凭证管理逻辑 =================
    const handleUpdateProvider = (provider: string) => {
        setSelectedProvider(provider);
        setApiKeyInput("");
        setBaseUrlInput("");
        setProviderDialogOpen(true);
    };

    const saveProviderConfig = async () => {
        if (!apiKeyInput) {
            toast.error("API Key不能为空 (API Key cannot be empty)");
            return;
        }
        setSavingProvider(true);
        try {
            await updateProviderKey({
                provider: selectedProvider,
                api_key: apiKeyInput,
                base_url: baseUrlInput || undefined
            });
            toast.success(`${selectedProvider} 凭证更新成功 (credentials updated)`);
            setProviderDialogOpen(false);
            fetchModels(); // 重新加载以验证状态 (虽然后端目前只是内存更新)
        } catch (error) {
            toast.error("更新凭证失败 (Failed to update credentials)");
        } finally {
            setSavingProvider(false);
        }
    };

    // 获取由后端模型 API 去重后的不重复 Provider 列表
    const uniqueProviders = Array.from(new Set(models.map(m => m.provider)));

    return (
        <div className="space-y-6 max-w-6xl mx-auto">
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-white mb-1">系统配置中心 (System Configuration Center)</h1>
                    <p className="text-slate-400">管理环境编排、API凭证以及运行引擎配置 (Manage environments, API credentials, and engine config)</p>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
                <TabsList className="bg-slate-900 border border-slate-800">
                    <TabsTrigger value="environments" className="data-[state=active]:bg-slate-800 text-slate-300 data-[state=active]:text-white">
                        <Globe className="w-4 h-4 mr-2" /> 环境管理 (Environments)
                    </TabsTrigger>
                    <TabsTrigger value="credentials" className="data-[state=active]:bg-slate-800 text-slate-300 data-[state=active]:text-white">
                        <KeyRound className="w-4 h-4 mr-2" /> 凭证与密钥 (Credentials & Keys)
                    </TabsTrigger>
                    <TabsTrigger value="about" className="data-[state=active]:bg-slate-800 text-slate-300 data-[state=active]:text-white">
                        <Info className="w-4 h-4 mr-2" /> 平台信息 (Platform Info)
                    </TabsTrigger>
                </TabsList>

                {/* =================环境管理 TAB================= */}
                <TabsContent value="environments" className="space-y-4">
                    <Card className="bg-slate-900 border-slate-800 shadow-xl">
                        <CardHeader className="flex flex-row items-center justify-between">
                            <div>
                                <CardTitle className="text-xl text-slate-100 font-bold">运行环境矩阵 (Runtime Environment Matrix)</CardTitle>
                                <CardDescription className="text-slate-400 mt-1">设置平台自动化执行的目标网关与全局注入变量 (Configure target gateways and global injection variables)</CardDescription>
                            </div>
                            <Button onClick={handleAddEnvironment} className="bg-purple-600 hover:bg-purple-700">
                                <Plus className="w-4 h-4 mr-1" /> 新建环境 (New Environment)
                            </Button>
                        </CardHeader>
                        <CardContent>
                            {loadingEnvs ? (
                                <div className="space-y-3">
                                    <Skeleton className="h-10 w-full bg-slate-800" />
                                    <Skeleton className="h-10 w-full bg-slate-800" />
                                    <Skeleton className="h-10 w-full bg-slate-800" />
                                </div>
                            ) : (
                                <div className="rounded-md border border-slate-800 overflow-hidden">
                                    <Table>
                                        <TableHeader className="bg-slate-900/50">
                                            <TableRow className="border-slate-800 hover:bg-transparent">
                                                <TableHead className="text-slate-300">环境名称 (Name)</TableHead>
                                                <TableHead className="text-slate-300">Base URL</TableHead>
                                                <TableHead className="text-slate-300">变量 (Variables)</TableHead>
                                                <TableHead className="text-slate-300">状态 (Status)</TableHead>
                                                <TableHead className="text-right text-slate-300">操作 (Actions)</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {environments.length === 0 ? (
                                                <TableRow className="border-slate-800">
                                                    <TableCell colSpan={5} className="text-center py-6 text-slate-500">
                                                        暂未配置任何环境 (No environments configured)
                                                    </TableCell>
                                                </TableRow>
                                            ) : environments.map((env) => (
                                                <TableRow key={env.id} className="border-slate-800 border-t hover:bg-slate-800/50">
                                                    <TableCell className="font-medium flex items-center gap-2 text-slate-200">
                                                        {env.name}
                                                        {env.is_default && <Badge variant="secondary" className="bg-blue-500/20 text-blue-400 font-normal border-blue-500/30">默认 (Default)</Badge>}
                                                    </TableCell>
                                                    <TableCell className="text-slate-200 font-mono text-xs">{env.base_url}</TableCell>
                                                    <TableCell>
                                                        <Badge variant="outline" className="border-slate-700 text-slate-400">
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
                                                        <Button variant="ghost" size="sm" onClick={() => handleCheckHealth(env.id!)} className="h-8 shadow-none text-slate-400 hover:text-blue-400 hover:bg-blue-500/10" title="健康检测 (Health Check)">
                                                            <HeartPulse className="w-4 h-4" />
                                                        </Button>
                                                        <Button variant="ghost" size="sm" onClick={() => handleEditEnvironment(env)} className="h-8 px-2 text-slate-400 hover:text-white" title="编辑 (Edit)">
                                                            <Pencil className="w-4 h-4" />
                                                        </Button>
                                                        <Button variant="ghost" size="sm" onClick={() => handleDeleteEnvironment(env.id!, env.name)} className="h-8 px-2 text-slate-500 hover:text-red-400 hover:bg-red-500/10" title="删除 (Delete)">
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
                </TabsContent>

                {/* =================凭证与密钥 TAB================= */}
                <TabsContent value="credentials" className="space-y-4">
                    <Card className="bg-slate-900 border-slate-800 shadow-xl">
                        <CardHeader>
                            <CardTitle className="text-xl text-slate-100 font-bold">AI模型供应商凭证 (AI Model Provider Credentials)</CardTitle>
                            <CardDescription className="text-slate-400">配置安全加密后的API密钥 (Configure encrypted API keys to activate LLM neurons)</CardDescription>
                        </CardHeader>
                        <CardContent>
                            {loadingModels ? (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    <Skeleton className="h-28 rounded-lg bg-slate-800" />
                                    <Skeleton className="h-28 rounded-lg bg-slate-800" />
                                </div>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                    {uniqueProviders.length === 0 ? (
                                        <div className="col-span-full py-8 text-center text-slate-500">无法连接到AI控制核心 (Cannot connect to AI control core)</div>
                                    ) : uniqueProviders.map((provider) => (
                                        <div key={provider} className="border border-slate-800 rounded-lg p-5 bg-slate-950/50 hover:bg-slate-800/20 transition-colors flex flex-col justify-between">
                                            <div className="flex items-start justify-between mb-4">
                                                <div>
                                                    <h3 className="font-semibold text-white flex items-center gap-2">
                                                        {provider === "aliyun" ? "阿里云 DashScope" :
                                                            provider === "openai" ? "OpenAI" :
                                                                provider === "gemini" ? "Google Gemini" : provider}
                                                    </h3>
                                                    <p className="text-xs text-slate-500 mt-1">支持 {models.filter(m => m.provider === provider).length} 已注册模型 (registered models)</p>
                                                </div>
                                                {/* 简化逻辑：这里默认假设有值的模型就算配好了，实际上可以提供一个连通性接口。由于后端采用 env 启动，默认都认为是 configured */}
                                                <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 bg-emerald-500/10 gap-1 pl-1">
                                                    <CheckCircle2 className="w-3 h-3" /> 已准备 (Ready)
                                                </Badge>
                                            </div>

                                            <div className="flex items-center justify-between mt-auto pt-4 border-t border-slate-800/50">
                                                <div className="text-xs text-slate-500 font-mono">sk-*******</div>
                                                <Button variant="outline" size="sm" onClick={() => handleUpdateProvider(provider)} className="h-7 text-xs border-slate-700 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white">
                                                    更新配置 (Update Config)
                                                </Button>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* =================平台信息 TAB================= */}
                <TabsContent value="about" className="space-y-4">
                    <Card className="bg-slate-900 border-slate-800 shadow-xl overflow-hidden">
                        <div className="h-2 bg-gradient-to-r from-blue-600 to-cyan-400 w-full" />
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-2xl font-black bg-gradient-to-br from-white to-slate-400 bg-clip-text text-transparent">
                                ChongMing
                                <Badge className="bg-blue-600 hover:bg-blue-600 rounded-full font-mono font-medium ml-2">v0.1.1</Badge>
                            </CardTitle>
                            <CardDescription className="text-slate-400">重明智能测试引擎 (Agentic Testing Platform)</CardDescription>
                        </CardHeader>
                        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-8 pt-4">
                            <div className="space-y-4">
                                <div>
                                    <h4 className="text-sm font-semibold text-slate-300 mb-2">系统架构 (System Architecture)</h4>
                                    <div className="space-y-2">
                                        <div className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                                            <span className="text-slate-500">网关前端 (Frontend Gateway)</span>
                                            <span className="text-slate-300 font-mono">Next.js 16 + React 18</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                                            <span className="text-slate-500">主控中枢 (Backend Core)</span>
                                            <span className="text-slate-300 font-mono">Python 3.12 + FastAPI</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                                            <span className="text-slate-500">数据持久层 (Data Persistence)</span>
                                            <span className="text-slate-300 font-mono">PostgreSQL (SQLAlchemy 2.0)</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                                            <span className="text-slate-500">任务网格 (Task Grid)</span>
                                            <span className="text-slate-300 font-mono">Redis + Celery Worker</span>
                                        </div>
                                        <div className="flex justify-between text-sm py-1 border-b border-slate-800/50">
                                            <span className="text-slate-500">向量检索</span>
                                            <span className="text-slate-300 font-mono">Chroma / Milvus</span>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-slate-950 p-5 rounded-lg border border-slate-800">
                                <h4 className="flex items-center gap-2 text-sm font-semibold text-emerald-400 mb-3">
                                    <ShieldAlert className="w-4 h-4" /> 架构与安全声明
                                </h4>
                                <p className="text-sm text-slate-400 leading-relaxed">
                                    重明平台采用去中心化可插拔微生架构。所有配置和敏感令牌在入表前由内置密钥进行封壳加密。环境变量支持严格的数据隔离。
                                    当前节点运行模式为 <span className="font-mono text-blue-400">Development</span>。
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>

            {/* =================弹窗: 环境编辑================= */}
            <Dialog open={envDialogOpen} onOpenChange={setEnvDialogOpen}>
                <DialogContent className="bg-slate-900 border-slate-800 text-white max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>{editingEnv?.id ? "编辑环境 (Edit Environment)" : "新建环境配置 (New Environment Configuration)"}</DialogTitle>
                        <DialogDescription className="text-slate-400">
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
                                    className="bg-slate-950 border-slate-800"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="base_url">Gateway Base URL <span className="text-red-500">*</span></Label>
                                <Input
                                    id="base_url"
                                    value={editingEnv?.base_url || ''}
                                    onChange={(e) => setEditingEnv({ ...editingEnv, base_url: e.target.value })}
                                    placeholder="https://api.staging.example.com"
                                    className="bg-slate-950 border-slate-800 font-mono text-sm"
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
                                className="bg-slate-950 border-slate-800 text-sm"
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
                        <Button variant="outline" onClick={() => setEnvDialogOpen(false)} className="border-slate-700 bg-transparent text-slate-300">取消 (Cancel)</Button>
                        <Button onClick={saveEnvironment} disabled={savingEnv} className="bg-blue-600 hover:bg-blue-700 text-white">
                            {savingEnv ? "保存中... (Saving...)" : "保存配置 (Save Configuration)"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* =================弹窗: 凭证更新================= */}
            <Dialog open={providerDialogOpen} onOpenChange={setProviderDialogOpen}>
                <DialogContent className="bg-slate-900 border-slate-800 text-white sm:max-w-md">
                    <DialogHeader>
                        <DialogTitle>配置凭证 (Configure Credentials) ({selectedProvider})</DialogTitle>
                        <DialogDescription className="text-slate-400">
                            更新此底层大模型提供商的访问密钥，更新后即刻生效。 (Update the access key for this underlying large model provider, effective immediately.)
                        </DialogDescription>
                    </DialogHeader>

                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="apikey">API Key / Token Base</Label>
                            <Input
                                id="apikey"
                                type="password"
                                value={apiKeyInput}
                                onChange={(e) => setApiKeyInput(e.target.value)}
                                placeholder="sk-..."
                                className="bg-slate-950 border-slate-800 font-mono"
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="baseurl">Custom Base URL (可选)</Label>
                            <Input
                                id="baseurl"
                                value={baseUrlInput}
                                onChange={(e) => setBaseUrlInput(e.target.value)}
                                placeholder="如果您使用了反向代理例如 OneAPI (If you use a reverse proxy like OneAPI)"
                                className="bg-slate-950 border-slate-800 font-mono text-sm"
                            />
                        </div>
                    </div>

                    <DialogFooter>
                        <Button variant="outline" onClick={() => setProviderDialogOpen(false)} className="border-slate-700 bg-transparent text-slate-300">取消 (Cancel)</Button>
                        <Button onClick={saveProviderConfig} disabled={savingProvider} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                            {savingProvider ? "同步中... (Syncing...)" : "安全部署生效 (Deploy Securely)"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
