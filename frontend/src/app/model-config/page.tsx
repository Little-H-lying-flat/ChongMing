"use client";

import React, { useEffect, useState } from "react";
import { Brain, Cpu, Key, Settings, Zap, CheckCircle2, DollarSign, Database, TrendingUp, BarChart3 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Legend } from 'recharts';
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import {
    getAvailableModels,
    getModuleConfigs,
    updateModuleConfig,
    updateProviderKey,
    getTokenUsageMetrics,
    AIModel,
    AIModuleConfig,
    TokenUsageMetric
} from "@/services/smartOpsService";

const MODULE_NAMES: Record<string, string> = {
    // === 通用 ===
    // === 通用 ===
    "general.chat": "平台通用对话 (Platform Chat)",
    "general.summary": "长文档摘要归纳 (Doc Summary)",
    "rag.embedding": "知识库文本向量化 (Embedding)",

    // === 角色智能体挂载点 (Agent Mount Points) - 神经设计层 ===
    "agent.neural.admin": "🧠设计层-主协调官 (Admin)",
    "agent.neural.finder": "🧠设计层-基建检索官 (Finder)",
    "agent.neural.ui_expert": "🧠设计层-前端体验专家 (UI Expert)",
    "agent.neural.api_expert": "🧠设计层-后端架构专家 (API Expert)",
    "agent.neural.merger": "🧠设计层-业务场景架构师 (Merger)",

    // === 角色智能体挂载点 (Agent Mount Points) - API执行引擎 (左瞳) ===
    "agent.left.sherlock": "🔌左瞳-接口诊断专家 (Sherlock)",
    "agent.left.healer": "🔌左瞳-自愈修复师 (Healer)",
    "agent.left.persona": "🔌左瞳-数据拟态师 (Persona)",
    "agent.left.red_teamer": "🔌左瞳-安全渗透师 (Red Teamer)",
    "agent.left.janitor": "🔌左瞳-数据清理工 (Janitor)",

    // === 角色智能体挂载点 (Agent Mount Points) - UI执行引擎 (右瞳) ===
    "agent.right.visual": "👁️右瞳-视觉交互专家 (Visual Expert)",
    "agent.right.persona": "👁️右瞳-视觉意图拆解 (Persona)",
    "agent.right.critic": "👁️右瞳-视觉审查官 (Critic)",
    "agent.right.sherlock": "👁️右瞳-DOM推断专家 (Sherlock)",
    "agent.right.healer": "👁️右瞳-交互纠偏师 (Healer)",
};

const getModuleName = (module: string) => MODULE_NAMES[module] || module;

export default function SmartOpsPage() {
    const [models, setModels] = useState<AIModel[]>([]);
    const [configs, setConfigs] = useState<AIModuleConfig[]>([]);
    const [metrics, setMetrics] = useState<TokenUsageMetric[]>([]);
    const [loading, setLoading] = useState(true);

    // Dialog state
    const [providerOpen, setProviderOpen] = useState(false);
    const [providerForm, setProviderForm] = useState({ provider: "openai", api_key: "", base_url: "" });

    // Routing state
    const [activeModule, setActiveModule] = useState<string>("");
    const [routeForm, setRouteForm] = useState<Partial<AIModuleConfig>>({});
    const [savingRoute, setSavingRoute] = useState(false);

    const fetchInitialData = async () => {
        try {
            setLoading(true);
            const [modelsData, configsData, metricsData] = await Promise.all([
                getAvailableModels(),
                getModuleConfigs(),
                getTokenUsageMetrics(7)
            ]);
            setModels(modelsData);
            setConfigs(configsData);
            setMetrics(metricsData);
            if (configsData.length > 0) {
                initRouteForm(configsData[0]);
            }
        } catch (error) {
            console.error(error);
            toast.error("加载模型治理数据失败 (Failed to load model governance data)");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchInitialData();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const initRouteForm = (config: AIModuleConfig) => {
        setActiveModule(config.module);
        setRouteForm({
            model_id: config.model_id,
            temperature: config.temperature ?? 0.7,
            max_tokens: config.max_tokens ?? 4096
        });
    };

    const handleProviderSave = async () => {
        if (!providerForm.api_key) {
            toast.error("API Key不能为空 (API Key cannot be empty)");
            return;
        }
        try {
            await updateProviderKey(providerForm);
            toast.success("Provider凭证已更新 (Provider credentials updated)");
            setProviderOpen(false);
            setProviderForm({ ...providerForm, api_key: "" });
        } catch (_error) {
            toast.error("更新Provider凭证失败 (Failed to update Provider credentials)");
        }
    };

    const handleRouteSave = async () => {
        if (!activeModule || !routeForm.model_id) return;

        setSavingRoute(true);
        try {
            const updatedConfig = await updateModuleConfig({
                module: activeModule,
                model_id: routeForm.model_id,
                temperature: routeForm.temperature,
                max_tokens: routeForm.max_tokens
            });

            // Update local state
            setConfigs(configs.map(c => c.module === activeModule ? updatedConfig : c));
            toast.success(`${getModuleName(activeModule)} 路由更新成功 (route updated)`);
        } catch (_error) {
            toast.error("更新模型路由失败 (Failed to update model route)");
        } finally {
            setSavingRoute(false);
        }
    };

    if (loading) {
        return (
            <div className="space-y-6">
                <div className="flex justify-between items-center">
                    <div><Skeleton className="h-8 w-48 bg-sky-50" /><Skeleton className="h-4 w-64 mt-2 bg-sky-50" /></div>
                </div>
                <Skeleton className="h-[400px] w-full bg-white/80 rounded-xl" />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-3xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-sky-600 via-blue-600 to-violet-600 flex items-center gap-2">
                        <Brain className="w-8 h-8 text-cyan-600" />
                        AI中枢治理 (AI Model Governance)
                    </h2>
                    <p className="text-slate-600 mt-1">
                        统一管控平台基础算力层与垂直场景的模型路由策略 (Unified model routing strategy management for base compute and vertical scenarios)
                    </p>
                </div>

                <Dialog open={providerOpen} onOpenChange={setProviderOpen}>
                    <DialogTrigger asChild>
                        <Button variant="outline" className="border-sky-200 bg-white/80 hover:bg-sky-50 text-slate-700">
                            <Key className="w-4 h-4 mr-2" /> 配置Provider凭证 (Configure Provider Credentials)
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="sm:max-w-[425px] bg-white/80 border-sky-100 text-slate-900">
                        <DialogHeader>
                            <DialogTitle>更新API访问凭证 (Update API Access Credentials)</DialogTitle>
                            <DialogDescription className="text-slate-600">
                                这些密钥将被加密存储且仅用于后端调用。 (Keys are encrypted and used only for backend calls.)
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="provider" className="text-right">供应商 (Provider)</Label>
                                <Select value={providerForm.provider} onValueChange={(v) => setProviderForm({ ...providerForm, provider: v })}>
                                    <SelectTrigger className="col-span-3 bg-white border-sky-200 text-slate-950">
                                        <SelectValue placeholder="选择供应商 (Select Provider)" />
                                    </SelectTrigger>
                                    <SelectContent className="bg-white/80 border-sky-200 text-slate-800">
                                        <SelectItem value="openai">OpenAI</SelectItem>
                                        <SelectItem value="azure">Azure Open AI</SelectItem>
                                        <SelectItem value="anthropic">Anthropic</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="api_key" className="text-right">API Key</Label>
                                <Input
                                    id="api_key" type="password"
                                    value={providerForm.api_key}
                                    onChange={(e) => setProviderForm({ ...providerForm, api_key: e.target.value })}
                                    className="col-span-3 bg-white border-sky-200 text-slate-800"
                                    placeholder="sk-..."
                                />
                            </div>
                            <div className="grid grid-cols-4 items-center gap-4">
                                <Label htmlFor="base_url" className="text-right">Base URL</Label>
                                <Input
                                    id="base_url" type="text"
                                    value={providerForm.base_url}
                                    onChange={(e) => setProviderForm({ ...providerForm, base_url: e.target.value })}
                                    className="col-span-3 bg-white border-sky-200 text-slate-800"
                                    placeholder="可选，支持私有代理/Azure (Optional, supports private proxy/Azure)"
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button type="submit" onClick={handleProviderSave} className="bg-gradient-to-r from-sky-500 to-cyan-500 text-white shadow-lg shadow-sky-500/20 hover:from-sky-600 hover:to-cyan-600">
                                保存更新 (Save Update)
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>

            <Tabs defaultValue="metrics" className="w-full">
                <TabsList className="bg-white/80 border border-sky-100 p-1">
                    <TabsTrigger value="metrics" className="text-slate-600 data-[state=active]:bg-emerald-50 data-[state=active]:text-emerald-700">
                        <BarChart3 className="w-4 h-4 mr-2" />
                        分析看板 (Metrics Dashboard)
                    </TabsTrigger>
                    <TabsTrigger value="dashboard" className="text-slate-600 data-[state=active]:bg-cyan-50 data-[state=active]:text-cyan-700">
                        <Cpu className="w-4 h-4 mr-2" />
                        基础算力池 (Model Dashboard)
                    </TabsTrigger>
                    <TabsTrigger value="routing" className="text-slate-600 data-[state=active]:bg-violet-50 data-[state=active]:text-violet-700">
                        <Settings className="w-4 h-4 mr-2" />
                        路由投递网 (Platform Routing)
                    </TabsTrigger>
                </TabsList>

                <TabsContent value="dashboard" className="mt-6">
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                        {models.map((model, idx) => (
                            <Card key={`${model.model_id}-${model.provider}-${idx}`} className="rounded-2xl border-sky-100 bg-white/80 shadow-[0_20px_60px_-35px_rgba(14,165,233,0.35)] backdrop-blur-xl relative overflow-hidden group hover:border-cyan-500/30 transition-colors">
                                <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                                <CardHeader className="pb-3 relative z-10">
                                    <div className="flex justify-between items-start">
                                        <div>
                                            <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                                                {model.model_id}
                                                {model.capability === 'vision' && <Badge variant="secondary" className="bg-violet-50 text-violet-700 border-violet-200 text-[10px] px-1.5 py-0">Vision</Badge>}
                                                {model.capability === 'chat' && <Badge variant="secondary" className="bg-sky-50 text-sky-700 border-sky-200 text-[10px] px-1.5 py-0">Reasoning</Badge>}
                                                {model.capability === 'embedding' && <Badge variant="secondary" className="bg-emerald-50 text-emerald-700 border-emerald-200 text-[10px] px-1.5 py-0">Vector</Badge>}
                                            </CardTitle>
                                            <CardDescription className="text-slate-600 mt-1">{model.provider.toUpperCase()} ENGINE</CardDescription>
                                        </div>
                                        <Badge variant="outline" className="border-cyan-200 text-cyan-700 bg-cyan-50">
                                            ${model.cost_per_1k_tokens.toFixed(3)}
                                        </Badge>
                                    </div>
                                </CardHeader>
                                <CardContent className="relative z-10">
                                    <p className="text-sm text-slate-500">{model.description}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                <TabsContent value="routing" className="mt-6 border border-sky-100 rounded-xl bg-white/70 p-0 overflow-hidden flex min-h-[500px]">
                    {/* Sidebar Modules */}
                    <div className="w-64 border-r border-sky-100 bg-white/75 p-4 space-y-2">
                        <h3 className="text-sm font-semibold text-slate-600 mb-4 px-2 tracking-wider">业务挂载点 (Business Mount Points)</h3>
                        {configs.map(config => (
                            <button
                                key={config.module}
                                onClick={() => initRouteForm(config)}
                                className={`w-full text-left px-4 py-3 rounded-md text-sm transition-colors flex justify-between items-center ${activeModule === config.module
                                    ? "bg-violet-50 text-violet-700 border border-violet-200 font-medium"
                                    : "text-slate-600 hover:bg-sky-50/80 hover:text-slate-700 border border-transparent"
                                    }`}
                            >
                                <span>{getModuleName(config.module)}</span>
                                {activeModule === config.module && <Zap className="w-3.5 h-3.5 text-violet-600 shrink-0 ml-2" />}
                            </button>
                        ))}
                    </div>

                    {/* Config Panel */}
                    <div className="flex-1 p-8">
                        {activeModule ? (
                            <div className="max-w-xl space-y-8 animate-in fade-in duration-300">
                                <div>
                                    <h3 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
                                        {getModuleName(activeModule)}
                                        <Badge variant="outline" className="ml-2 border-emerald-500/30 text-emerald-400 bg-emerald-500/5">生效中 (Active)</Badge>
                                    </h3>
                                    <p className="text-slate-600 text-sm mt-2">
                                        在此调整该业务节点使用的基础模型与推理参数，生效周期为即时。 (Adjust the base model and reasoning parameters used by this business node here, effective immediately.)
                                    </p>
                                </div>

                                <div className="space-y-6 bg-white/80 p-6 rounded-xl border border-sky-100/50 shadow-inner">
                                    {/* Model Selection */}
                                    <div className="space-y-3">
                                        <Label className="text-slate-700">投递目标 (Target Model)</Label>
                                        <Select
                                            value={routeForm.model_id}
                                            onValueChange={(v) => setRouteForm({ ...routeForm, model_id: v })}
                                        >
                                            <SelectTrigger className="w-full bg-white border-sky-200 text-slate-950 font-medium h-12">
                                                <SelectValue placeholder="Select a model..." />
                                            </SelectTrigger>
                                            <SelectContent className="bg-white/80 border-sky-200 text-slate-800">
                                                {models.map((m, idx) => (
                                                    <SelectItem key={`${m.model_id}-${m.provider}-${idx}`} value={m.model_id}>
                                                        <div className="flex items-center gap-2">
                                                            {m.model_id} <span className="text-xs text-slate-500">({m.provider})</span>
                                                        </div>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Temperature Slider */}
                                    <div className="space-y-4 pt-4">
                                        <div className="flex justify-between">
                                            <Label className="text-slate-700">Temperature (想象力: {routeForm.temperature?.toFixed(1)})</Label>
                                        </div>
                                        <Slider
                                            value={[routeForm.temperature || 0]}
                                            max={2}
                                            step={0.1}
                                            onValueChange={(val) => setRouteForm({ ...routeForm, temperature: val[0] })}
                                            className="py-2"
                                        />
                                        <div className="flex justify-between text-[10px] text-slate-500 pt-1">
                                            <span>Strict (0.0)</span>
                                            <span>Creative (2.0)</span>
                                        </div>
                                    </div>

                                    {/* Max Tokens */}
                                    <div className="space-y-3 pt-4">
                                        <Label className="text-slate-700">截断阈值 (Max Tokens)</Label>
                                        <Input
                                            type="number"
                                            max={32000}
                                            value={routeForm.max_tokens || ""}
                                            onChange={(e) => setRouteForm({ ...routeForm, max_tokens: parseInt(e.target.value) || 0 })}
                                            className="bg-white border-sky-200 text-slate-800 font-mono"
                                        />
                                    </div>
                                </div>

                                <div className="pt-4 flex items-center gap-4">
                                    <Button
                                        onClick={handleRouteSave}
                                        disabled={savingRoute}
                                        className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/25 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600 min-w-[120px]"
                                    >
                                        {savingRoute ? "更新中... (Updating...)" : <><CheckCircle2 className="w-4 h-4 mr-2" /> 应用策略 (Apply Strategy)</>}
                                    </Button>
                                    <span className="text-xs text-slate-500">配置将被立刻同步至底层的 Redis 路由中心。 (The configuration will be synchronized immediately to the underlying Redis routing center.)</span>
                                </div>
                            </div>
                        ) : (
                            <div className="h-full flex items-center justify-center text-slate-500 flex-col">
                                <Settings className="w-12 h-12 mb-4 opacity-20" />
                                <p>请在左侧选择一个业务挂载点 (Please select a business mount point on the left)</p>
                            </div>
                        )}
                    </div>
                </TabsContent>

                <TabsContent value="metrics" className="mt-6 space-y-6">
                    {/* KPI Cards */}
                    {(() => {
                        const totalCost = metrics.reduce((sum, day) => sum + day.cost, 0);
                        const totalTokens = metrics.reduce((sum, day) => sum + Object.entries(day).reduce((acc, [k, v]) => {
                            return (k !== 'date' && k !== 'cost' && typeof v === 'number') ? acc + v : acc;
                        }, 0), 0);

                        const modelTotals: Record<string, number> = {};
                        metrics.forEach(day => {
                            Object.entries(day).forEach(([k, v]) => {
                                if (k !== 'date' && k !== 'cost' && typeof v === 'number') {
                                    modelTotals[k] = (modelTotals[k] || 0) + v;
                                }
                            });
                        });
                        const topModel = Object.entries(modelTotals).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A';
                        const uniqueModels = Object.keys(modelTotals);
                        const chartColors = ["#8b5cf6", "#06b6d4", "#10b981", "#f59e0b", "#ec4899", "#3b82f6"];

                        return (
                            <>
                                <div className="grid gap-4 md:grid-cols-3">
                                    <Card className="rounded-2xl border-sky-100 bg-white/80 backdrop-blur-sm bg-opacity-80">
                                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                                            <CardTitle className="text-sm font-medium text-slate-600">总计支出 (7天) (Total Expenditure (7 days))</CardTitle>
                                            <DollarSign className="w-4 h-4 text-emerald-400" />
                                        </CardHeader>
                                        <CardContent>
                                            <div className="text-2xl font-bold text-slate-900">${totalCost.toFixed(4)}</div>
                                            <p className="text-xs text-slate-500 mt-1">等效 API 账单成本 (Equivalent API Billing Cost)</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl border-sky-100 bg-white/80 backdrop-blur-sm bg-opacity-80">
                                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                                            <CardTitle className="text-sm font-medium text-slate-600">资源消耗 (7天) (Resource Consumption (7 days))</CardTitle>
                                            <Database className="w-4 h-4 text-cyan-600" />
                                        </CardHeader>
                                        <CardContent>
                                            <div className="text-2xl font-bold text-slate-900">{(totalTokens / 1000).toFixed(1)}k <span className="text-sm text-slate-500 font-normal">Tokens</span></div>
                                            <p className="text-xs text-slate-500 mt-1">包含 Input/Output 总计 (Total Input/Output Included)</p>
                                        </CardContent>
                                    </Card>
                                    <Card className="rounded-2xl border-sky-100 bg-white/80 backdrop-blur-sm bg-opacity-80">
                                        <CardHeader className="flex flex-row items-center justify-between pb-2">
                                            <CardTitle className="text-sm font-medium text-slate-600">最高负载网关 (Highest Load Gateway)</CardTitle>
                                            <TrendingUp className="w-4 h-4 text-violet-600" />
                                        </CardHeader>
                                        <CardContent>
                                            <div className="text-2xl font-bold text-slate-900">{topModel}</div>
                                            <p className="text-xs text-slate-500 mt-1">分担最高流量的模型 (Model sharing the highest traffic)</p>
                                        </CardContent>
                                    </Card>
                                </div>

                                <Card className="rounded-2xl border-sky-100 bg-white/80 mt-6 backdrop-blur-sm bg-opacity-80">
                                    <CardHeader>
                                        <CardTitle className="text-lg text-slate-800">每日 Token 消耗聚合分析 (Daily Token Consumption Aggregate Analysis)</CardTitle>
                                        <CardDescription className="text-slate-600">堆叠比例反映各基础模型当日的请求配额占比 (The stacking ratio reflects the proportion of each base model&apos;s request quota on that day)</CardDescription>
                                    </CardHeader>
                                    <CardContent>
                                        {metrics.length === 0 ? (
                                            <div className="h-[350px] flex items-center justify-center flex-col text-slate-500">
                                                <BarChart3 className="w-12 h-12 mb-4 opacity-20" />
                                                <p>过去 7 天内暂无调用数据 (No call data in the past 7 days)</p>
                                            </div>
                                        ) : (
                                            <div className="h-[350px] w-full mt-4">
                                                <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
                                                    <BarChart data={metrics} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                                                        <XAxis dataKey="date" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                                                        <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `${(val / 1000).toFixed(1)}k`} />
                                                        <RechartsTooltip
                                                            contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b', borderRadius: '8px' }}
                                                            itemStyle={{ color: '#e2e8f0' }}
                                                            labelStyle={{ color: '#94a3b8', marginBottom: '8px' }}
                                                            formatter={(value: number | string | undefined, name: string | undefined) => [`${value ?? 0} Tokens`, name ?? '']}
                                                        />
                                                        <Legend wrapperStyle={{ paddingTop: '20px' }} />
                                                        {uniqueModels.map((modelId, idx) => (
                                                            <Bar key={modelId} dataKey={modelId} stackId="a" fill={chartColors[idx % chartColors.length]} />
                                                        ))}
                                                    </BarChart>
                                                </ResponsiveContainer>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </>
                        );
                    })()}
                </TabsContent>
            </Tabs>
        </div>
    );
}
