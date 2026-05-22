"use client"

import React, { useEffect, useState } from 'react';
import { AlertTriangle, ClipboardList, Database, FileJson, FileSearch, ListChecks, Plus, RefreshCw, Save, Search, ShieldCheck, Sparkles } from "lucide-react";
import { format } from "date-fns";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
    GenerateAssetDraftsResponse,
    JsonObject,
    ReviewItem,
    ScanCampaign,
    ScanCampaignCreate,
    ScanCampaignPlan,
    scanCampaignService,
} from '@/services/scanCampaignService';

type CampaignFormState = {
    name: string;
    base_url: string;
    business_module: string;
    scope_text: string;
    out_of_scope_text: string;
    notes: string;
    scan_mode: string;
    intensity: string;
    allowed_domains: string;
    allowed_paths: string;
    forbidden_actions: string;
    confirmation_required_actions: string;
    environment_safety: string;
    write_policy: string;
};

const DEFAULT_FORM: CampaignFormState = {
    name: "用户管理 Smoke 灰盒扫描",
    base_url: "https://staging.example.com",
    business_module: "用户管理",
    scope_text: "登录、用户列表、新建用户",
    out_of_scope_text: "删除用户、重置密码、发送邀请短信",
    notes: "Phase 1 只生成计划和资产草稿，不自动执行测试。",
    scan_mode: "graybox",
    intensity: "smoke",
    allowed_domains: "staging.example.com",
    allowed_paths: "/login\n/users\n/api/users",
    forbidden_actions: "delete\npayment\nsend_sms\nsend_email",
    confirmation_required_actions: "POST /api/users",
    environment_safety: "staging",
    write_policy: "allow_test_data",
};

const choiceLabels: Record<string, string> = {
    pending: "待复核",
    skip: "跳过",
    generate_asset_only: "只生成资产草稿",
    approve_for_future_execution: "保存未来执行意向",
};

const policyLabels: Record<string, string> = {
    allowed: "允许生成草稿",
    confirmation_required: "需要人工确认",
    conditional_allowed: "条件允许",
    forbidden: "禁止",
    out_of_scope: "超出范围",
};

const splitLines = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);

const joinLines = (value: unknown) => Array.isArray(value)
    ? value.map((item) => String(item)).join("\n")
    : "";

const getText = (value: unknown, fallback = "") => typeof value === "string" ? value : fallback;

const getNumberText = (value: unknown) => typeof value === "number" ? value.toFixed(2) : "-";

const formatDate = (value?: string | null) => {
    if (!value) return "-";
    try {
        return format(new Date(value), "yyyy-MM-dd HH:mm");
    } catch {
        return value;
    }
};

const getPolicyClassName = (policy: string) => {
    if (policy === "forbidden") return "border-red-200 bg-red-50 text-red-700";
    if (policy === "confirmation_required") return "border-amber-200 bg-amber-50 text-amber-700";
    if (policy === "conditional_allowed") return "border-blue-200 bg-blue-50 text-blue-700";
    if (policy === "out_of_scope") return "border-slate-200 bg-slate-50 text-slate-600";
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
};

const JsonPreview = ({ data }: { data: unknown }) => (
    <pre className="max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-relaxed text-slate-100">
        {JSON.stringify(data, null, 2)}
    </pre>
);

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
    <label className="space-y-2 text-sm font-medium text-slate-700">
        <span>{label}</span>
        {children}
    </label>
);

const formFromCampaign = (campaign: ScanCampaign): CampaignFormState => ({
    name: campaign.name,
    base_url: getText(campaign.target.base_url),
    business_module: getText(campaign.target.business_module),
    scope_text: getText(campaign.target.scope_text),
    out_of_scope_text: getText(campaign.target.out_of_scope_text),
    notes: getText(campaign.target.notes),
    scan_mode: getText(campaign.strategy.scan_mode, "graybox"),
    intensity: getText(campaign.strategy.intensity, "smoke"),
    allowed_domains: joinLines(campaign.boundaries.allowed_domains),
    allowed_paths: joinLines(campaign.boundaries.allowed_paths),
    forbidden_actions: joinLines(campaign.action_policy.forbidden_actions),
    confirmation_required_actions: joinLines(campaign.action_policy.confirmation_required_actions),
    environment_safety: getText(campaign.data_policy.environment_safety, "staging"),
    write_policy: getText(campaign.data_policy.write_policy, "allow_test_data"),
});

const buildCampaignPayload = (form: CampaignFormState): ScanCampaignCreate => ({
    name: form.name.trim(),
    target: {
        base_url: form.base_url.trim(),
        business_module: form.business_module.trim(),
        scope_text: form.scope_text.trim(),
        out_of_scope_text: form.out_of_scope_text.trim(),
        notes: form.notes.trim(),
    },
    strategy: {
        scan_mode: form.scan_mode,
        intensity: form.intensity,
        output_goals: ["test_plan", "pre_execution_checklist"],
        generate_asset_drafts: false,
    },
    boundaries: {
        allowed_domains: splitLines(form.allowed_domains),
        allowed_paths: splitLines(form.allowed_paths),
        max_pages: 10,
        max_api_candidates: 20,
        max_plan_steps: 30,
    },
    action_policy: {
        forbidden_actions: splitLines(form.forbidden_actions),
        confirmation_required_actions: splitLines(form.confirmation_required_actions),
        conditional_allowed_actions: ["仅允许写入 test_user_* 测试数据"],
        form_submit_policy: "confirm_required",
        write_api_policy: "confirm_required",
    },
    data_policy: {
        environment_safety: form.environment_safety,
        credential_source: "environment",
        write_policy: form.write_policy,
        test_data_markers: ["test_user_*"],
        cleanup_policy: "manual_cleanup",
    },
    special_limits: {
        upload: { allowed_types: ["png", "jpg"], max_size_mb: 2 },
        export: { max_rows: 100, field_allowlist: ["id"] },
        payment: { provider_policy: "mock_or_sandbox_only" },
    },
});

export default function SmartScanPage() {
    const [campaigns, setCampaigns] = useState<ScanCampaign[]>([]);
    const [activeCampaign, setActiveCampaign] = useState<ScanCampaign | null>(null);
    const [currentPlan, setCurrentPlan] = useState<ScanCampaignPlan | null>(null);
    const [assetDrafts, setAssetDrafts] = useState<GenerateAssetDraftsResponse | null>(null);
    const [form, setForm] = useState<CampaignFormState>(DEFAULT_FORM);
    const [reviewDrafts, setReviewDrafts] = useState<Record<string, { choice: string; comment: string }>>({});
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
    const [isSavingReview, setIsSavingReview] = useState<string | null>(null);
    const [isGeneratingDrafts, setIsGeneratingDrafts] = useState(false);

    const loadLatestPlan = React.useCallback(async (campaignId: string) => {
        try {
            const res = await scanCampaignService.getLatestPlan(campaignId);
            setCurrentPlan(res.data);
        } catch {
            setCurrentPlan(null);
        }
    }, []);

    const loadCampaigns = React.useCallback(async (preferredId?: string) => {
        setIsLoadingList(true);
        try {
            const res = await scanCampaignService.listCampaigns({ page: 1, pageSize: 20 });
            const items = res.data.items || [];
            setCampaigns(items);
            const selected = items.find((item) => item.id === preferredId) || items[0] || null;
            if (selected) {
                setActiveCampaign(selected);
                setForm(formFromCampaign(selected));
                setAssetDrafts(null);
                void loadLatestPlan(selected.id);
            } else {
                setActiveCampaign(null);
                setCurrentPlan(null);
            }
        } catch (err: unknown) {
            const error = err as { message?: string };
            toast.error("加载 Campaign 失败", { description: error.message });
        } finally {
            setIsLoadingList(false);
        }
    }, [loadLatestPlan]);

    useEffect(() => {
        void loadCampaigns();
    }, [loadCampaigns]);

    useEffect(() => {
        if (!currentPlan) {
            setReviewDrafts({});
            return;
        }

        const nextDrafts: Record<string, { choice: string; comment: string }> = {};
        currentPlan.manual_review_items.forEach((item) => {
            nextDrafts[item.id] = {
                choice: item.choice === "pending" ? "" : item.choice,
                comment: item.comment || "",
            };
        });
        setReviewDrafts(nextDrafts);
    }, [currentPlan]);

    const updateForm = (field: keyof CampaignFormState, value: string) => {
        setForm((current) => ({ ...current, [field]: value }));
    };

    const selectCampaign = (campaign: ScanCampaign) => {
        setActiveCampaign(campaign);
        setForm(formFromCampaign(campaign));
        setAssetDrafts(null);
        void loadLatestPlan(campaign.id);
    };

    const handleNewCampaign = () => {
        setActiveCampaign(null);
        setCurrentPlan(null);
        setAssetDrafts(null);
        setForm(DEFAULT_FORM);
    };

    const validateForm = () => {
        if (!form.name.trim()) return "请填写 Campaign 名称";
        if (!form.base_url.trim()) return "请填写目标 URL";
        if (splitLines(form.allowed_domains).length === 0) return "请至少填写一个允许域名";
        if (splitLines(form.allowed_paths).length === 0) return "请至少填写一个允许路径";
        return null;
    };

    const handleSaveCampaign = async () => {
        const validationError = validateForm();
        if (validationError) {
            toast.error(validationError);
            return null;
        }

        const payload = buildCampaignPayload(form);
        setIsSaving(true);
        try {
            let saved: ScanCampaign;
            if (activeCampaign && ["draft", "needs_revision"].includes(activeCampaign.status)) {
                const res = await scanCampaignService.updateCampaign(activeCampaign.id, payload);
                saved = res.data;
                toast.success("Campaign 草稿已保存");
            } else {
                const res = await scanCampaignService.createCampaign(payload);
                saved = res.data;
                toast.success("Campaign 草稿已创建");
            }

            setActiveCampaign(saved);
            setForm(formFromCampaign(saved));
            await loadCampaigns(saved.id);
            return saved;
        } catch (err: unknown) {
            toast.error("保存 Campaign 失败", { description: (err as { message?: string }).message });
            return null;
        } finally {
            setIsSaving(false);
        }
    };

    const handleGeneratePlan = async () => {
        const campaign = activeCampaign || await handleSaveCampaign();
        if (!campaign) return;

        setIsGeneratingPlan(true);
        setAssetDrafts(null);
        try {
            const res = await scanCampaignService.generatePlan(campaign.id, { notes: form.notes || undefined });
            setCurrentPlan(res.data);
            toast.success("AI 计划已生成，请先复核风险项");
            await loadCampaigns(campaign.id);
        } catch (err: unknown) {
            toast.error("生成 AI 计划失败", { description: (err as { message?: string }).message });
        } finally {
            setIsGeneratingPlan(false);
        }
    };

    const updateReviewDraft = (itemId: string, field: "choice" | "comment", value: string) => {
        setReviewDrafts((current) => ({
            ...current,
            [itemId]: {
                choice: current[itemId]?.choice || "",
                comment: current[itemId]?.comment || "",
                [field]: value,
            },
        }));
    };

    const handleSaveReview = async (item: ReviewItem) => {
        if (!activeCampaign || !currentPlan) return;
        const draft = reviewDrafts[item.id];
        if (!draft?.choice) {
            toast.error("请选择复核结论");
            return;
        }

        setIsSavingReview(item.id);
        try {
            await scanCampaignService.updateReviewItem(activeCampaign.id, currentPlan.plan_id, item.id, {
                choice: draft.choice,
                comment: draft.comment || undefined,
            });
            toast.success("复核选择已保存");
            await loadLatestPlan(activeCampaign.id);
        } catch (err: unknown) {
            toast.error("保存复核选择失败", { description: (err as { message?: string }).message });
        } finally {
            setIsSavingReview(null);
        }
    };

    const handleGenerateAssetDrafts = async () => {
        if (!activeCampaign || !currentPlan) {
            toast.error("请先生成 AI 计划");
            return;
        }

        setIsGeneratingDrafts(true);
        try {
            const res = await scanCampaignService.generateAssetDrafts(activeCampaign.id, currentPlan.plan_id, {
                asset_types: ["api_case_ir", "visual_ui_case"],
                include_only_approved: true,
            });
            setAssetDrafts(res.data);
            await loadLatestPlan(activeCampaign.id);
            toast.success("资产草稿预览已生成");
        } catch (err: unknown) {
            toast.error("生成资产草稿预览失败", { description: (err as { message?: string }).message });
        } finally {
            setIsGeneratingDrafts(false);
        }
    };

    const renderPolicyBadge = (policy: string) => (
        <Badge variant="outline" className={getPolicyClassName(policy)}>
            {policyLabels[policy] || policy}
        </Badge>
    );

    const renderCandidate = (candidate: JsonObject, index: number) => {
        const policy = getText(candidate.policy, "allowed");
        return (
            <Card key={getText(candidate.id, String(index))} className="border-slate-200 bg-white/80 py-4">
                <CardContent className="space-y-3 px-4">
                    <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">{getText(candidate.method, "GET")}</Badge>
                        <span className="font-mono text-sm text-slate-800">{getText(candidate.path, "/")}</span>
                        {renderPolicyBadge(policy)}
                    </div>
                    <p className="text-sm text-slate-600">{getText(candidate.summary, "未提供摘要")}</p>
                    <div className="grid gap-2 text-xs text-slate-500 md:grid-cols-2">
                        <div>来源：{getText(candidate.source, "-")}</div>
                        <div>匹配分：{getNumberText(candidate.match_score)}</div>
                        <div className="md:col-span-2">风险原因：{getText(candidate.risk_reason, "-")}</div>
                    </div>
                    <JsonPreview data={{ match_reasons: candidate.match_reasons, source_ref: candidate.source_ref, conditions: candidate.conditions }} />
                </CardContent>
            </Card>
        );
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-sky-50 to-violet-50 p-6 text-slate-900">
            <div className="mx-auto flex max-w-7xl flex-col gap-6">
                <Card className="border-sky-100 bg-white/85 shadow-xl shadow-sky-100/60 backdrop-blur">
                    <CardContent className="flex flex-col gap-4 px-6 md:flex-row md:items-center md:justify-between">
                        <div className="space-y-2">
                            <div className="flex items-center gap-3">
                                <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-500 to-violet-500 text-white shadow-lg shadow-sky-500/20">
                                    <Search className="h-5 w-5" />
                                </div>
                                <div>
                                    <h1 className="text-2xl font-bold text-slate-950">智能扫描 (Smart Scan)</h1>
                                    <p className="text-sm text-slate-500">自然语言范围 + URL + API Asset 候选，生成可复核计划和资产草稿。</p>
                                </div>
                            </div>
                            <div className="flex flex-wrap gap-2 text-xs">
                                <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">Phase 1 仅生成计划和草稿</Badge>
                                <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">写操作默认需人工确认</Badge>
                                <Badge variant="outline" className="border-red-200 bg-red-50 text-red-700">删除、支付、消息发送默认禁止</Badge>
                            </div>
                        </div>
                        <Button variant="outline" onClick={() => void loadCampaigns(activeCampaign?.id)} disabled={isLoadingList} className="gap-2">
                            <RefreshCw className="h-4 w-4" />
                            刷新 Campaign
                        </Button>
                    </CardContent>
                </Card>

                <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                    <Card className="border-sky-100 bg-white/85 shadow-lg shadow-sky-100/50">
                        <CardHeader className="gap-3">
                            <div className="flex items-center justify-between gap-3">
                                <CardTitle className="flex items-center gap-2 text-base">
                                    <ClipboardList className="h-4 w-4 text-sky-600" />
                                    Campaign 列表
                                </CardTitle>
                                <Button size="sm" onClick={handleNewCampaign} className="gap-2">
                                    <Plus className="h-4 w-4" />
                                    新建
                                </Button>
                            </div>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {isLoadingList ? (
                                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">正在加载 Campaign...</div>
                            ) : campaigns.length === 0 ? (
                                <div className="rounded-xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">暂无 Campaign，先创建一个草稿。</div>
                            ) : campaigns.map((campaign) => (
                                <button
                                    key={campaign.id}
                                    type="button"
                                    onClick={() => selectCampaign(campaign)}
                                    className={`w-full rounded-xl border p-4 text-left transition ${activeCampaign?.id === campaign.id
                                        ? "border-sky-300 bg-sky-50 shadow-sm"
                                        : "border-slate-200 bg-white hover:border-sky-200 hover:bg-sky-50/60"
                                        }`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <div className="space-y-1">
                                            <div className="font-medium text-slate-900">{campaign.name}</div>
                                            <div className="text-xs text-slate-500">{getText(campaign.target.business_module, "未设置模块")}</div>
                                        </div>
                                        <Badge variant="outline" className="border-slate-200 bg-white text-slate-600">{campaign.status}</Badge>
                                    </div>
                                    <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                                        <span>{getText(campaign.strategy.scan_mode, "-")}</span>
                                        <span>·</span>
                                        <span>{formatDate(campaign.updated_at)}</span>
                                    </div>
                                </button>
                            ))}
                        </CardContent>
                    </Card>

                    <Tabs defaultValue="draft" className="gap-4">
                        <TabsList className="grid h-auto w-full grid-cols-2 gap-2 bg-white/70 p-2 shadow-sm md:grid-cols-4">
                            <TabsTrigger value="draft" className="gap-2"><FileSearch className="h-4 w-4" />Campaign 草稿</TabsTrigger>
                            <TabsTrigger value="plan" className="gap-2"><Sparkles className="h-4 w-4" />AI 计划</TabsTrigger>
                            <TabsTrigger value="review" className="gap-2"><ListChecks className="h-4 w-4" />人工复核</TabsTrigger>
                            <TabsTrigger value="drafts" className="gap-2"><Database className="h-4 w-4" />资产草稿</TabsTrigger>
                        </TabsList>

                        <TabsContent value="draft">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle>Campaign 草稿</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="grid gap-4 md:grid-cols-2">
                                        <Field label="Campaign 名称">
                                            <Input value={form.name} onChange={(event) => updateForm("name", event.target.value)} />
                                        </Field>
                                        <Field label="目标 URL">
                                            <Input value={form.base_url} onChange={(event) => updateForm("base_url", event.target.value)} />
                                        </Field>
                                        <Field label="业务模块">
                                            <Input value={form.business_module} onChange={(event) => updateForm("business_module", event.target.value)} />
                                        </Field>
                                        <div className="grid gap-4 sm:grid-cols-2">
                                            <Field label="测试模式">
                                                <Select value={form.scan_mode} onValueChange={(value) => updateForm("scan_mode", value)}>
                                                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="blackbox">blackbox</SelectItem>
                                                        <SelectItem value="graybox">graybox</SelectItem>
                                                        <SelectItem value="whitebox">whitebox</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </Field>
                                            <Field label="强度">
                                                <Select value={form.intensity} onValueChange={(value) => updateForm("intensity", value)}>
                                                    <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="smoke">smoke</SelectItem>
                                                        <SelectItem value="standard">standard</SelectItem>
                                                        <SelectItem value="deep">deep</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </Field>
                                        </div>
                                    </div>

                                    <div className="grid gap-4 md:grid-cols-2">
                                        <Field label="范围描述">
                                            <Textarea className="min-h-28" value={form.scope_text} onChange={(event) => updateForm("scope_text", event.target.value)} />
                                        </Field>
                                        <Field label="排除范围">
                                            <Textarea className="min-h-28" value={form.out_of_scope_text} onChange={(event) => updateForm("out_of_scope_text", event.target.value)} />
                                        </Field>
                                        <Field label="允许域名（每行一个）">
                                            <Textarea className="min-h-24 font-mono" value={form.allowed_domains} onChange={(event) => updateForm("allowed_domains", event.target.value)} />
                                        </Field>
                                        <Field label="允许路径（每行一个）">
                                            <Textarea className="min-h-24 font-mono" value={form.allowed_paths} onChange={(event) => updateForm("allowed_paths", event.target.value)} />
                                        </Field>
                                        <Field label="禁止动作（每行一个）">
                                            <Textarea className="min-h-24 font-mono" value={form.forbidden_actions} onChange={(event) => updateForm("forbidden_actions", event.target.value)} />
                                        </Field>
                                        <Field label="需确认动作（每行一个）">
                                            <Textarea className="min-h-24 font-mono" value={form.confirmation_required_actions} onChange={(event) => updateForm("confirmation_required_actions", event.target.value)} />
                                        </Field>
                                        <Field label="环境安全级别">
                                            <Select value={form.environment_safety} onValueChange={(value) => updateForm("environment_safety", value)}>
                                                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="staging">staging</SelectItem>
                                                    <SelectItem value="production-readonly">production-readonly</SelectItem>
                                                    <SelectItem value="sandbox">sandbox</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </Field>
                                        <Field label="写入策略">
                                            <Select value={form.write_policy} onValueChange={(value) => updateForm("write_policy", value)}>
                                                <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="allow_test_data">allow_test_data</SelectItem>
                                                    <SelectItem value="readonly">readonly</SelectItem>
                                                    <SelectItem value="manual_confirm">manual_confirm</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </Field>
                                        <Field label="补充说明">
                                            <Textarea className="min-h-24" value={form.notes} onChange={(event) => updateForm("notes", event.target.value)} />
                                        </Field>
                                    </div>

                                    <div className="flex flex-wrap gap-3">
                                        <Button onClick={() => void handleSaveCampaign()} disabled={isSaving} className="gap-2">
                                            <Save className="h-4 w-4" />
                                            保存 Campaign 草稿
                                        </Button>
                                        <Button variant="secondary" onClick={() => void handleGeneratePlan()} disabled={isSaving || isGeneratingPlan} className="gap-2">
                                            <Sparkles className="h-4 w-4" />
                                            生成 AI 计划
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="plan">
                            <div className="space-y-4">
                                {!currentPlan ? (
                                    <Card className="border-dashed border-slate-200 bg-white/80">
                                        <CardContent className="flex items-center gap-3 px-6 text-sm text-slate-500">
                                            <Sparkles className="h-5 w-5 text-sky-500" />
                                            请先保存 Campaign 草稿并生成 AI 计划。
                                        </CardContent>
                                    </Card>
                                ) : (
                                    <>
                                        <Card className="border-sky-100 bg-white/90">
                                            <CardHeader>
                                                <CardTitle className="flex items-center justify-between gap-3">
                                                    <span>计划概览</span>
                                                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">v{currentPlan.version} · {currentPlan.status}</Badge>
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="grid gap-4 md:grid-cols-2">
                                                <JsonPreview data={currentPlan.summary} />
                                                <JsonPreview data={currentPlan.coverage_summary} />
                                            </CardContent>
                                        </Card>

                                        <Card className="border-sky-100 bg-white/90">
                                            <CardHeader><CardTitle>API 候选</CardTitle></CardHeader>
                                            <CardContent className="space-y-3">
                                                {currentPlan.api_candidates.length === 0 ? (
                                                    <p className="text-sm text-slate-500">暂无 API 候选。</p>
                                                ) : currentPlan.api_candidates.map(renderCandidate)}
                                            </CardContent>
                                        </Card>

                                        <div className="grid gap-4 xl:grid-cols-2">
                                            <Card className="border-sky-100 bg-white/90">
                                                <CardHeader><CardTitle>UI 流程草稿</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={currentPlan.ui_flows} /></CardContent>
                                            </Card>
                                            <Card className="border-sky-100 bg-white/90">
                                                <CardHeader><CardTitle>风险项</CardTitle></CardHeader>
                                                <CardContent className="space-y-3">
                                                    {currentPlan.risk_items.length === 0 ? (
                                                        <p className="text-sm text-slate-500">暂无风险项。</p>
                                                    ) : currentPlan.risk_items.map((item, index) => {
                                                        const policy = getText(item.policy, "allowed");
                                                        return (
                                                            <div key={`${getText(item.id, "risk")}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
                                                                <div className="mb-2 flex items-center gap-2">{renderPolicyBadge(policy)}</div>
                                                                <JsonPreview data={item} />
                                                            </div>
                                                        );
                                                    })}
                                                </CardContent>
                                            </Card>
                                        </div>
                                    </>
                                )}
                            </div>
                        </TabsContent>

                        <TabsContent value="review">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <ShieldCheck className="h-5 w-5 text-emerald-600" />
                                        人工复核
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {!currentPlan ? (
                                        <p className="text-sm text-slate-500">请先生成 AI 计划。</p>
                                    ) : currentPlan.manual_review_items.length === 0 ? (
                                        <p className="text-sm text-slate-500">暂无待复核项。</p>
                                    ) : currentPlan.manual_review_items.map((item) => {
                                        const draft = reviewDrafts[item.id] || { choice: "", comment: "" };
                                        return (
                                            <Card key={item.id} className="border-slate-200 bg-white py-4">
                                                <CardContent className="space-y-4 px-4">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        {renderPolicyBadge(item.policy)}
                                                        <Badge variant="outline" className="border-slate-200 bg-slate-50 text-slate-600">{choiceLabels[item.choice] || item.choice}</Badge>
                                                    </div>
                                                    <div>
                                                        <h3 className="font-semibold text-slate-900">{item.title}</h3>
                                                        <p className="mt-1 text-sm text-slate-600">{item.reason}</p>
                                                    </div>
                                                    <div className="grid gap-3 rounded-xl border border-slate-100 bg-slate-50 p-3 text-sm text-slate-600 md:grid-cols-2">
                                                        <div><span className="font-medium text-slate-800">通过后：</span>{item.if_approved}</div>
                                                        <div><span className="font-medium text-slate-800">拒绝后：</span>{item.if_rejected}</div>
                                                    </div>
                                                    <div className="grid gap-3 md:grid-cols-[260px_1fr_auto] md:items-end">
                                                        <Field label="复核选择">
                                                            <Select value={draft.choice || undefined} onValueChange={(value) => updateReviewDraft(item.id, "choice", value)}>
                                                                <SelectTrigger className="w-full"><SelectValue placeholder="请选择" /></SelectTrigger>
                                                                <SelectContent>
                                                                    {item.available_choices.map((choice) => (
                                                                        <SelectItem key={choice} value={choice}>{choiceLabels[choice] || choice}</SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </Field>
                                                        <Field label="备注">
                                                            <Input value={draft.comment} onChange={(event) => updateReviewDraft(item.id, "comment", event.target.value)} />
                                                        </Field>
                                                        <Button onClick={() => void handleSaveReview(item)} disabled={isSavingReview === item.id} className="gap-2">
                                                            <Save className="h-4 w-4" />
                                                            保存复核选择
                                                        </Button>
                                                    </div>
                                                    <div className="flex items-start gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs text-amber-700">
                                                        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                                                        approve_for_future_execution 只保存未来意向，Phase 1 不触发真实测试流程。
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        );
                                    })}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="drafts">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <FileJson className="h-5 w-5 text-sky-600" />
                                        资产草稿预览
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-sky-100 bg-sky-50 p-4 text-sm text-sky-800">
                                        <span>草稿预览只保存到 Scan Campaign 草稿表，不写入正式 API Auto 或 Visual UI 用例。</span>
                                        <Button onClick={() => void handleGenerateAssetDrafts()} disabled={isGeneratingDrafts || !currentPlan} className="gap-2">
                                            <Database className="h-4 w-4" />
                                            生成资产草稿预览
                                        </Button>
                                    </div>

                                    {!assetDrafts ? (
                                        <p className="text-sm text-slate-500">生成后将在这里展示 API Case IR v2、Visual UI 草稿和跳过项。</p>
                                    ) : (
                                        <div className="space-y-4">
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">API Case IR v2 草稿</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts.api_case_ir_steps} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">Visual UI 草稿</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts.visual_ui_cases} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">跳过项</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts.skipped_items} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">草稿元信息</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts.asset_drafts} /></CardContent>
                                            </Card>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>
                    </Tabs>
                </div>
            </div>
        </div>
    );
}
