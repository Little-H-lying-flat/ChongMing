"use client"

import React, { useEffect, useState } from 'react';
import { ClipboardList, Database, FileJson, FileSearch, ListChecks, PlayCircle, Plus, RefreshCw, Save, Search, ShieldCheck, Sparkles } from "lucide-react";
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
    AssetDraft,
    AssetPromotion,
    ConfirmExecutionResponse,
    GenerateAssetDraftsResponse,
    SmartScanExecutionSummaryResponse,
    SmartScanReportResponse,
    JsonObject,
    PromoteAssetDraftsResponse,
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

type FriendlyError = {
    title: string;
    reason: string;
    recovery: string;
};

type NoticeTone = "info" | "success" | "warning" | "error";

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

const campaignStatusLabels: Record<string, string> = {
    draft: "Campaign 草稿",
    plan_generated: "AI 计划已生成",
    review_saved: "复核已保存",
    asset_drafts_generated: "资产草稿已生成",
    needs_revision: "需要修订",
    archived: "已归档",
};

const planStatusLabels: Record<string, string> = {
    generated: "AI 计划已生成",
    review_saved: "复核已保存",
    asset_drafts_generated: "资产草稿已生成",
    superseded: "已被新版本替代",
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

const getFriendlyErrorDetail = (err: unknown): FriendlyError => {
    const message = (err as { message?: string })?.message || "请稍后重试";
    if (message.includes("draft_ids 不能为空")) {
        return {
            title: "请先选择资产草稿",
            reason: "保存正式资产需要至少勾选一个尚未保存的草稿。",
            recovery: "在资产草稿列表中勾选 API 或 Visual UI 草稿后再保存。",
        };
    }
    if (message.includes("already_promoted")) {
        return {
            title: "草稿已经保存过",
            reason: "后端检测到该 draft id 已经关联正式资产。",
            recovery: "刷新草稿状态，查看已保存的正式资产 ID；系统不会重复创建。",
        };
    }
    if (message.includes("404")) {
        return {
            title: "资源或接口不存在",
            reason: "当前后端可能不是最新版本，或 Campaign / Plan / Draft 已被刷新。",
            recovery: "确认后端运行最新代码，然后刷新 Campaign 列表再试。",
        };
    }
    if (message.includes("409")) {
        return {
            title: "当前状态不允许该操作",
            reason: "Campaign 或 Plan 已进入另一个阶段，不能重复执行当前动作。",
            recovery: "刷新 Campaign，查看当前阶段后继续下一步。",
        };
    }
    if (message.includes("400")) {
        return {
            title: "请求内容不符合要求",
            reason: "必填字段、范围边界或确认标记缺失。",
            recovery: "检查 Campaign 表单、人工复核选择和草稿勾选状态后重试。",
        };
    }
    if (message.includes("Failed to fetch")) {
        return {
            title: "无法连接后端服务",
            reason: "前端没有连到 Smart Scan API。",
            recovery: "检查后端是否运行，以及 NEXT_PUBLIC_API_URL 是否指向正确地址。",
        };
    }
    return {
        title: "操作失败",
        reason: message,
        recovery: "请根据提示修正后重试；如果状态不一致，先刷新 Campaign。",
    };
};

const noticeClassNames: Record<NoticeTone, string> = {
    info: "border-sky-100 bg-sky-50 text-sky-800",
    success: "border-emerald-100 bg-emerald-50 text-emerald-800",
    warning: "border-amber-100 bg-amber-50 text-amber-800",
    error: "border-red-100 bg-red-50 text-red-800",
};

const InlineNotice = ({ tone = "info", title, children }: { tone?: NoticeTone; title?: string; children: React.ReactNode }) => (
    <div role="status" aria-live="polite" className={`rounded-xl border px-4 py-3 text-sm ${noticeClassNames[tone]}`}>
        {title ? <div className="font-semibold">{title}</div> : null}
        <div className={title ? "mt-1" : ""}>{children}</div>
    </div>
);

const InlineError = ({ error }: { error: FriendlyError | null }) => {
    if (!error) return null;
    return (
        <div role="alert" className="rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-800">
            <div className="font-semibold">{error.title}</div>
            <div className="mt-1">原因：{error.reason}</div>
            <div className="mt-1">处理方式：{error.recovery}</div>
        </div>
    );
};

const EmptyState = ({ title, description }: { title: string; description: string }) => (
    <div role="status" className="rounded-xl border border-dashed border-slate-200 bg-white/70 p-5 text-sm">
        <div className="font-medium text-slate-800">{title}</div>
        <div className="mt-1 text-slate-500">{description}</div>
    </div>
);

const JsonPreview = ({ data }: { data: unknown }) => (
    <pre className="max-h-80 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-relaxed text-slate-100">
        {JSON.stringify(data, null, 2)}
    </pre>
);

const StatusMetric = ({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) => (
    <div className="rounded-xl border border-slate-200 bg-white/80 p-3 text-sm">
        <div className="text-xs text-slate-500">{label}</div>
        <div className="mt-1 text-lg font-bold text-slate-950">{value}</div>
        {hint ? <div className="mt-1 text-xs text-slate-500">{hint}</div> : null}
    </div>
);

const ActionHint = ({ children }: { children?: React.ReactNode }) => {
    if (!children) return null;
    return <p className="mt-2 text-xs text-slate-500">{children}</p>;
};

const Field = ({ label, hint, required, children }: { label: string; hint?: string; required?: boolean; children: React.ReactNode }) => (
    <label className="space-y-2 text-sm font-medium text-slate-700">
        <span>
            {label}
            {required ? <span className="ml-1 text-red-600">必填</span> : null}
        </span>
        {children}
        {hint ? <span className="block text-xs font-normal text-slate-500">{hint}</span> : null}
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

const getReviewChoiceDescription = (choice: string) => {
    if (choice === "skip") return "不生成资产，也不会进入后续保存流程。";
    if (choice === "generate_asset_only") return "只生成资产草稿，可在 Phase 2 保存为正式资产，但不会执行测试。";
    if (choice === "approve_for_future_execution") return "仅保存未来执行意向；真正执行仍需 Phase 3 执行前确认页再次授权。";
    return "请选择一个复核结论后才能保存。";
};

const getDraftPayloadSummary = (draft: AssetDraft) => {
    const payload = draft.draft_payload || {};
    if (draft.asset_type === "visual_ui_case") {
        const steps = Array.isArray(payload.steps) ? payload.steps.length : 0;
        return {
            title: getText(payload.name, "Visual UI 草稿"),
            line: `base_url：${getText(payload.base_url, "-")} · steps：${steps}`,
        };
    }
    const request = (payload.request || {}) as JsonObject;
    const method = getText(request.method, getText(payload.method, "GET"));
    const path = getText(request.path, getText(request.url, getText(payload.path, "/")));
    const assertion = (payload.assertion || {}) as JsonObject;
    return {
        title: getText(payload.name, `${method} ${path}`),
        line: `${method} ${path} · 期望状态：${getText(assertion.status_code, "-")}`,
    };
};

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
    const [assetDraftRows, setAssetDraftRows] = useState<AssetDraft[]>([]);
    const [assetPromotions, setAssetPromotions] = useState<AssetPromotion[]>([]);
    const [selectedDraftIds, setSelectedDraftIds] = useState<string[]>([]);
    const [selectedPromotionIds, setSelectedPromotionIds] = useState<string[]>([]);
    const [promotionResult, setPromotionResult] = useState<PromoteAssetDraftsResponse | null>(null);
    const [executionAuthorizationChecked, setExecutionAuthorizationChecked] = useState(false);
    const [executionResult, setExecutionResult] = useState<ConfirmExecutionResponse | null>(null);
    const [executionSummary, setExecutionSummary] = useState<SmartScanExecutionSummaryResponse | null>(null);
    const [smartScanReport, setSmartScanReport] = useState<SmartScanReportResponse | null>(null);
    const [isLoadingExecutionSummary, setIsLoadingExecutionSummary] = useState(false);
    const [isLoadingReport, setIsLoadingReport] = useState(false);
    const [form, setForm] = useState<CampaignFormState>(DEFAULT_FORM);
    const [reviewDrafts, setReviewDrafts] = useState<Record<string, { choice: string; comment: string }>>({});
    const [activeTab, setActiveTab] = useState("draft");
    const [lastActionMessage, setLastActionMessage] = useState("Phase 2 可将草稿手动保存为正式资产，但仍然不会执行测试。");
    const [lastError, setLastError] = useState<FriendlyError | null>(null);
    const [isLoadingList, setIsLoadingList] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
    const [isSavingReview, setIsSavingReview] = useState<string | null>(null);
    const [isGeneratingDrafts, setIsGeneratingDrafts] = useState(false);
    const [isPromotingDrafts, setIsPromotingDrafts] = useState(false);
    const [isConfirmingExecution, setIsConfirmingExecution] = useState(false);

    const loadAssetDraftState = React.useCallback(async (campaignId: string, planId: string) => {
        try {
            const [draftRes, promotionRes] = await Promise.all([
                scanCampaignService.listAssetDrafts(campaignId, planId),
                scanCampaignService.listAssetPromotions(campaignId, planId),
            ]);
            setAssetDraftRows(draftRes.data.items || []);
            setAssetPromotions(promotionRes.data.items || []);
            setSelectedDraftIds((current) => current.filter((id) => draftRes.data.items.some((draft) => draft.id === id)));
            setSelectedPromotionIds((current) => current.filter((id) => promotionRes.data.items.some((promotion) => promotion.id === id)));
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            setAssetDraftRows([]);
            setAssetPromotions([]);
            setSelectedDraftIds([]);
            setSelectedPromotionIds([]);
            setLastError(detail);
            toast.error("加载资产草稿状态失败", { description: `${detail.reason} ${detail.recovery}` });
        }
    }, []);

    const loadExecutionSummary = React.useCallback(async (campaignId: string, planId: string) => {
        setIsLoadingExecutionSummary(true);
        try {
            const res = await scanCampaignService.getExecutionSummary(campaignId, planId);
            setExecutionSummary(res.data);
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            setExecutionSummary(null);
            setLastError(detail);
            toast.error("加载执行结果失败", { description: `${detail.reason} ${detail.recovery}` });
        } finally {
            setIsLoadingExecutionSummary(false);
        }
    }, []);

    const loadSmartScanReport = React.useCallback(async (campaignId: string, planId: string) => {
        setIsLoadingReport(true);
        try {
            const res = await scanCampaignService.getReport(campaignId, planId);
            setSmartScanReport(res.data);
            setLastError(null);
            toast.success("Smart Scan 报告已生成", { description: "可复制 Markdown 或 JSON 用于复盘展示。" });
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            setSmartScanReport(null);
            setLastError(detail);
            toast.error("生成报告失败", { description: `${detail.reason} ${detail.recovery}` });
        } finally {
            setIsLoadingReport(false);
        }
    }, []);

    const loadLatestPlan = React.useCallback(async (campaignId: string) => {
        try {
            const res = await scanCampaignService.getLatestPlan(campaignId);
            setCurrentPlan(res.data);
            await loadAssetDraftState(campaignId, res.data.plan_id);
            await loadExecutionSummary(campaignId, res.data.plan_id);
            if (res.data.status === "asset_drafts_generated") {
                setActiveTab("drafts");
            } else if (res.data.manual_review_items.some((item) => item.choice !== "pending")) {
                setActiveTab("review");
            } else {
                setActiveTab("plan");
            }
        } catch {
            setCurrentPlan(null);
            setAssetDraftRows([]);
            setAssetPromotions([]);
            setSelectedDraftIds([]);
            setSelectedPromotionIds([]);
            setExecutionSummary(null);
            setSmartScanReport(null);
            setActiveTab("draft");
        }
    }, [loadAssetDraftState, loadExecutionSummary]);

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
                setPromotionResult(null);
                void loadLatestPlan(selected.id);
            } else {
                setActiveCampaign(null);
                setCurrentPlan(null);
                setAssetDraftRows([]);
                setAssetPromotions([]);
                setSelectedDraftIds([]);
                setSelectedPromotionIds([]);
                setExecutionSummary(null);
                setSmartScanReport(null);
                setActiveTab("draft");
            }
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            setLastError(detail);
            toast.error("加载 Campaign 失败", { description: `${detail.reason} ${detail.recovery}` });
            setLastActionMessage(detail.recovery);
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
        setPromotionResult(null);
        setSelectedPromotionIds([]);
        setExecutionAuthorizationChecked(false);
        setExecutionResult(null);
        setExecutionSummary(null);
        setSmartScanReport(null);
        void loadLatestPlan(campaign.id);
    };

    const handleNewCampaign = () => {
        setActiveCampaign(null);
        setCurrentPlan(null);
        setAssetDrafts(null);
        setAssetDraftRows([]);
        setAssetPromotions([]);
        setSelectedDraftIds([]);
        setSelectedPromotionIds([]);
        setPromotionResult(null);
        setExecutionAuthorizationChecked(false);
        setExecutionResult(null);
        setExecutionSummary(null);
        setSmartScanReport(null);
        setForm(DEFAULT_FORM);
        setActiveTab("draft");
        setLastError(null);
        setLastActionMessage("已进入新建 Campaign 草稿，保存后才能生成 AI 计划。");
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
            const detail = {
                title: "Campaign 草稿缺少必填信息",
                reason: validationError,
                recovery: "补齐字段后再保存；当前阶段不会执行测试。",
            };
            setLastError(detail);
            toast.error(detail.title, { description: detail.reason });
            return null;
        }

        const payload = buildCampaignPayload(form);
        setIsSaving(true);
        try {
            let saved: ScanCampaign;
            if (activeCampaign && ["draft", "needs_revision"].includes(activeCampaign.status)) {
                const res = await scanCampaignService.updateCampaign(activeCampaign.id, payload);
                saved = res.data;
                toast.success("Campaign 草稿已保存", { description: "可继续生成 AI 计划；当前不会执行测试。" });
                setLastError(null);
                setLastActionMessage("Campaign 草稿已保存，可继续生成 AI 计划。");
            } else {
                const res = await scanCampaignService.createCampaign(payload);
                saved = res.data;
                toast.success("Campaign 草稿已创建", { description: "可继续生成 AI 计划；当前不会执行测试。" });
                setLastError(null);
                setLastActionMessage("Campaign 草稿已创建，可继续生成 AI 计划。");
            }

            setActiveCampaign(saved);
            setForm(formFromCampaign(saved));
            await loadCampaigns(saved.id);
            return saved;
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("保存 Campaign 失败", { description });
            setLastActionMessage(detail.recovery);
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
            setActiveTab("plan");
            setLastError(null);
            setLastActionMessage("AI 计划已生成，请先查看候选项和风险项，再进入人工复核。");
            toast.success("AI 计划已生成", { description: "请先复核风险项；当前不会执行测试。" });
            await loadCampaigns(campaign.id);
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("生成 AI 计划失败", { description });
            setLastActionMessage(detail.recovery);
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
            const detail = {
                title: "请选择复核结论",
                reason: "该风险项还没有明确选择跳过、只生成草稿或保存未来意向。",
                recovery: "先选择一个复核结论，再保存该项；当前阶段不会执行测试。",
            };
            setLastError(detail);
            toast.error(detail.title, { description: detail.reason });
            return;
        }

        setIsSavingReview(item.id);
        try {
            await scanCampaignService.updateReviewItem(activeCampaign.id, currentPlan.plan_id, item.id, {
                choice: draft.choice,
                comment: draft.comment || undefined,
            });
            setLastError(null);
            setLastActionMessage(`复核选择已保存：${choiceLabels[draft.choice] || draft.choice}。该选择只影响草稿生成，不会触发执行。`);
            toast.success("复核选择已保存", { description: "该选择只影响草稿生成，不会触发执行。" });
            await loadLatestPlan(activeCampaign.id);
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("保存复核选择失败", { description });
            setLastActionMessage(detail.recovery);
        } finally {
            setIsSavingReview(null);
        }
    };

    const handleGenerateAssetDrafts = async () => {
        if (!activeCampaign || !currentPlan) {
            const detail = {
                title: "请先生成 AI 计划",
                reason: "资产草稿需要基于当前 Campaign 的 AI 计划生成。",
                recovery: "返回 Campaign 草稿，保存后点击“生成 AI 计划”。",
            };
            setLastError(detail);
            toast.error(detail.title, { description: detail.reason });
            return;
        }

        setIsGeneratingDrafts(true);
        try {
            const res = await scanCampaignService.generateAssetDrafts(activeCampaign.id, currentPlan.plan_id, {
                asset_types: ["api_case_ir", "visual_ui_case"],
                include_only_approved: true,
            });
            setAssetDrafts(res.data);
            setAssetDraftRows(res.data.asset_drafts || []);
            setSelectedDraftIds([]);
            setSelectedPromotionIds([]);
            setPromotionResult(null);
            setActiveTab("drafts");
            setLastError(null);
            setLastActionMessage(`资产草稿预览已生成：API ${res.data.api_case_ir_steps.length} 个，Visual UI ${res.data.visual_ui_cases.length} 个。保存正式资产仍不会执行测试。`);
            await loadAssetDraftState(activeCampaign.id, currentPlan.plan_id);
            await loadLatestPlan(activeCampaign.id);
            toast.success("资产草稿预览已生成", { description: "草稿不会自动执行，需确认后才保存为正式资产。" });
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("生成资产草稿预览失败", { description });
            setLastActionMessage(detail.recovery);
        } finally {
            setIsGeneratingDrafts(false);
        }
    };

    const handleToggleDraft = (draftId: string) => {
        setSelectedDraftIds((current) => current.includes(draftId)
            ? current.filter((id) => id !== draftId)
            : [...current, draftId]);
    };

    const handleTogglePromotion = (promotionId: string) => {
        setSelectedPromotionIds((current) => current.includes(promotionId)
            ? current.filter((id) => id !== promotionId)
            : [...current, promotionId]);
    };

    const handleConfirmExecution = async () => {
        if (!activeCampaign || !currentPlan || selectedPromotionIds.length === 0 || !executionAuthorizationChecked) return;
        const confirmed = window.confirm(`确认授权执行 ${selectedPromotionIds.length} 个已保存资产？\n\n后端会重新校验范围和策略，通过后才创建 Execution 并进入调度。`);
        if (!confirmed) return;

        setIsConfirmingExecution(true);
        try {
            const res = await scanCampaignService.confirmExecution(activeCampaign.id, currentPlan.plan_id, {
                promotion_ids: selectedPromotionIds,
                confirmation: 'AUTHORIZE_SMART_SCAN_EXECUTION',
                parallel: false,
                max_workers: 1,
            });
            setExecutionResult(res.data);
            setSelectedPromotionIds([]);
            setExecutionAuthorizationChecked(false);
            await loadExecutionSummary(activeCampaign.id, currentPlan.plan_id);
            setActiveTab("results");
            setLastError(null);
            setLastActionMessage(`Phase 3 已授权创建 Execution：${res.data.execution_id}，共 ${res.data.total_cases} 个用例。`);
            toast.success("执行已创建", { description: `Execution ${res.data.execution_id} 已进入调度。` });
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("创建执行失败", { description });
            setLastActionMessage(detail.recovery);
        } finally {
            setIsConfirmingExecution(false);
        }
    };

    const handleCopyReportMarkdown = async () => {
        if (!smartScanReport?.markdown) return;
        await navigator.clipboard.writeText(smartScanReport.markdown);
        toast.success("Markdown 已复制", { description: "可以粘贴到复盘文档或面试展示材料。" });
    };

    const handleCopyReportJson = async () => {
        if (!smartScanReport) return;
        await navigator.clipboard.writeText(JSON.stringify(smartScanReport, null, 2));
        toast.success("JSON 已复制", { description: "已复制完整 Smart Scan 报告数据。" });
    };

    const handlePromoteDrafts = async () => {
        if (!activeCampaign || !currentPlan || selectedDraftIds.length === 0) return;
        const confirmed = window.confirm(`确认保存 ${selectedDraftIds.length} 个草稿为正式资产？\n\n这些资产会进入 API Auto / Visual UI，但不会自动执行测试。已保存过的草稿会被跳过。`);
        if (!confirmed) return;

        setIsPromotingDrafts(true);
        try {
            const res = await scanCampaignService.promoteAssetDrafts(activeCampaign.id, currentPlan.plan_id, {
                draft_ids: selectedDraftIds,
                confirmation: 'PROMOTE_SELECTED_DRAFTS',
                visual_project_id: 'default',
            });
            setPromotionResult(res.data);
            setSelectedDraftIds([]);
            setSelectedPromotionIds([]);
            setExecutionResult(null);
            setLastError(null);
            await loadAssetDraftState(activeCampaign.id, currentPlan.plan_id);
            setActiveTab("execution");
            const createdCount = res.data.promoted.length;
            const duplicateCount = res.data.duplicates.length;
            setLastActionMessage(`正式资产保存完成：新建 ${createdCount} 个，已保存跳过 ${duplicateCount} 个；没有执行测试。`);
            toast.success("正式资产保存完成", { description: `新建 ${createdCount} 个，已保存跳过 ${duplicateCount} 个；没有执行测试。` });
        } catch (err: unknown) {
            const detail = getFriendlyErrorDetail(err);
            const description = `${detail.reason} ${detail.recovery}`;
            setLastError(detail);
            toast.error("保存正式资产失败", { description });
            setLastActionMessage(detail.recovery);
        } finally {
            setIsPromotingDrafts(false);
        }
    };

    const promotionByDraftId = React.useMemo(() => {
        const map = new Map<string, AssetPromotion>();
        assetPromotions.forEach((promotion) => map.set(promotion.asset_draft_id, promotion));
        return map;
    }, [assetPromotions]);

    const renderPolicyBadge = (policy: string) => (
        <Badge variant="outline" className={getPolicyClassName(policy)}>
            {policyLabels[policy] || policy}
        </Badge>
    );

    const currentStageIndex = !activeCampaign
        ? 1
        : (executionSummary?.total_executions || 0) > 0
            ? 6
            : assetPromotions.length > 0
                ? 5
                : currentPlan?.status === "asset_drafts_generated" || activeCampaign.status === "asset_drafts_generated"
                    ? 4
                    : currentPlan?.manual_review_items.some((item) => item.choice !== "pending")
                        ? 3
                        : currentPlan
                            ? 2
                            : 1;

    const planAssetDrafts = currentPlan?.asset_drafts as { api_case_ir_steps?: JsonObject[]; visual_ui_steps?: JsonObject[] } | undefined;
    const displayedApiDrafts = assetDrafts?.api_case_ir_steps || planAssetDrafts?.api_case_ir_steps || [];
    const displayedVisualDrafts = assetDrafts?.visual_ui_cases || planAssetDrafts?.visual_ui_steps || [];
    const displayedDraftRows = assetDraftRows.length ? assetDraftRows : assetDrafts?.asset_drafts || [];
    const reviewTotal = currentPlan?.manual_review_items.length || 0;
    const reviewSaved = currentPlan?.manual_review_items.filter((item) => item.choice !== "pending").length || 0;
    const promotedCount = assetPromotions.length;
    const executablePromotions = assetPromotions.filter((promotion) => promotion.status === "created");
    const stageItems = [
        { index: 1, label: "Campaign 草稿", readyReason: activeCampaign ? "已保存 Campaign" : "请先保存 Campaign" },
        { index: 2, label: "AI 计划", readyReason: currentPlan ? "已生成 AI 计划" : "请先生成 AI 计划" },
        { index: 3, label: "人工复核", readyReason: currentPlan ? `${reviewSaved}/${reviewTotal} 项已保存` : "需要 AI 计划" },
        { index: 4, label: "资产草稿", readyReason: displayedDraftRows.length ? `${displayedDraftRows.length} 个草稿` : "请先生成草稿预览" },
        { index: 5, label: "执行确认", readyReason: executablePromotions.length ? `${executablePromotions.length} 个已保存资产` : "请先保存正式资产" },
        { index: 6, label: "结果闭环", readyReason: executionSummary?.total_executions ? `${executionSummary.total_executions} 次执行` : "等待执行结果" },
    ];
    const currentStageLabel = stageItems.find((stage) => stage.index === currentStageIndex)?.label || "Campaign 草稿";
    const nextStepHint = !activeCampaign
        ? "先保存 Campaign 草稿，然后生成 AI 计划。"
        : !currentPlan
            ? "下一步：生成 AI 计划；当前不会执行测试。"
            : reviewTotal > reviewSaved
                ? "下一步：完成人工复核，明确哪些项只生成资产草稿。"
                : displayedDraftRows.length === 0
                    ? "下一步：生成资产草稿预览。"
                    : (executionSummary?.total_executions || 0) > 0
                        ? "下一步：进入结果闭环，查看执行历史并生成 Smart Scan 报告。"
                        : assetPromotions.length > 0
                            ? "下一步：进入执行确认页，选择已保存资产并明确授权后才会创建 Execution。"
                            : selectedDraftIds.length > 0
                                ? "下一步：保存所选草稿为正式资产；保存不会执行测试。"
                                : "下一步：勾选未保存草稿，或查看已保存正式资产。";
    const formValidationMessage = validateForm();
    const saveCampaignHint = isSaving ? "正在保存 Campaign 草稿。" : formValidationMessage || undefined;
    const generatePlanHint = isGeneratingPlan
        ? "正在生成 AI 计划。"
        : !activeCampaign && formValidationMessage
            ? "缺少必填字段时无法生成 AI 计划。"
            : undefined;
    const generateDraftHint = !currentPlan ? "需要先生成 AI 计划。" : isGeneratingDrafts ? "正在生成资产草稿预览。" : undefined;
    const promoteHint = selectedDraftIds.length === 0 ? "请先勾选至少一个尚未保存的草稿。" : isPromotingDrafts ? "正在保存正式资产。" : undefined;
    const confirmExecutionHint = executablePromotions.length === 0
        ? "请先在 Phase 2 保存正式资产。"
        : selectedPromotionIds.length === 0
            ? "请先选择至少一个已保存资产。"
            : !executionAuthorizationChecked
                ? "请勾选授权声明。"
                : isConfirmingExecution
                    ? "正在创建 Execution。"
                    : undefined;

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

                <Card className="border-sky-100 bg-white/85 shadow-lg shadow-sky-100/50">
                    <CardContent className="space-y-4 px-6">
                        <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                            <div>
                                <div className="text-sm font-semibold text-slate-900">
                                    {activeCampaign ? activeCampaign.name : "新建 Campaign 草稿"}
                                </div>
                                <div className="mt-1 text-xs text-slate-500">
                                    Campaign：{activeCampaign ? campaignStatusLabels[activeCampaign.status] || activeCampaign.status : "未保存"}
                                    {currentPlan ? ` · Plan：${planStatusLabels[currentPlan.status] || currentPlan.status}` : " · Plan：未生成"}
                                </div>
                            </div>
                            <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">当前阶段：{currentStageLabel}</Badge>
                        </div>
                        <div className="grid gap-3 md:grid-cols-4">
                            <StatusMetric label="复核进度" value={`${reviewSaved}/${reviewTotal}`} hint={currentPlan ? "已保存复核项" : "等待 AI 计划"} />
                            <StatusMetric label="完整草稿" value={displayedDraftRows.length} hint="可保存的 draft row" />
                            <StatusMetric label="已保存资产" value={promotedCount} hint="正式 API / Visual UI 资产" />
                            <StatusMetric label="已选草稿" value={selectedDraftIds.length} hint="保存前可调整" />
                        </div>
                        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
                            {stageItems.map((stage) => {
                                const tabValue = ["draft", "plan", "review", "drafts", "execution", "results"][stage.index - 1];
                                const isCurrent = currentStageIndex === stage.index;
                                const isComplete = currentStageIndex > stage.index;
                                return (
                                    <button
                                        key={stage.index}
                                        type="button"
                                        aria-current={isCurrent ? "step" : undefined}
                                        onClick={() => setActiveTab(tabValue)}
                                        className={`min-h-16 rounded-xl border px-3 py-2 text-left text-sm transition ${currentStageIndex >= stage.index
                                            ? "border-sky-200 bg-sky-50 text-sky-800"
                                            : "border-slate-200 bg-white text-slate-500"
                                            } ${activeTab === tabValue ? "ring-2 ring-sky-200" : ""}`}
                                    >
                                        <div><span className="font-semibold">{stage.index}. </span>{stage.label}</div>
                                        <div className="mt-1 text-xs opacity-80">{isCurrent ? "当前" : isComplete ? "已完成" : "待完成"} · {stage.readyReason}</div>
                                    </button>
                                );
                            })}
                        </div>
                        <InlineNotice tone={lastError ? "warning" : "success"}>
                            {lastActionMessage} {nextStepHint}
                        </InlineNotice>
                        <InlineError error={lastError} />
                    </CardContent>
                </Card>

                <div className="grid min-w-0 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
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
                                <EmptyState title="正在加载 Campaign" description="请稍等，正在读取最近的智能扫描草稿。" />
                            ) : campaigns.length === 0 ? (
                                <EmptyState title="还没有 Campaign" description="先创建一个扫描范围草稿，Phase 1.5 只会生成计划和草稿。" />
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
                                        <Badge variant="outline" className="border-slate-200 bg-white text-slate-600">{campaignStatusLabels[campaign.status] || campaign.status}</Badge>
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

                    <Tabs value={activeTab} onValueChange={setActiveTab} className="min-w-0 gap-4">
                        <TabsList className="sticky top-0 z-10 grid h-auto w-full min-w-0 grid-cols-2 gap-2 bg-white/90 p-2 shadow-sm backdrop-blur md:grid-cols-3 xl:grid-cols-6">
                            <TabsTrigger value="draft" className="gap-2"><FileSearch className="h-4 w-4" />Campaign 草稿</TabsTrigger>
                            <TabsTrigger value="plan" className="gap-2"><Sparkles className="h-4 w-4" />AI 计划</TabsTrigger>
                            <TabsTrigger value="review" className="gap-2"><ListChecks className="h-4 w-4" />人工复核</TabsTrigger>
                            <TabsTrigger value="drafts" className="gap-2"><Database className="h-4 w-4" />资产草稿</TabsTrigger>
                            <TabsTrigger value="execution" className="gap-2"><PlayCircle className="h-4 w-4" />执行确认</TabsTrigger>
                            <TabsTrigger value="results" className="gap-2"><ShieldCheck className="h-4 w-4" />结果闭环</TabsTrigger>
                        </TabsList>

                        <TabsContent value="draft">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle>Campaign 草稿</CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-6">
                                    <div className="grid gap-4 md:grid-cols-2">
                                        <Field label="Campaign 名称" required hint="用于识别本次 Smart Scan 范围。">
                                            <Input value={form.name} onChange={(event) => updateForm("name", event.target.value)} />
                                        </Field>
                                        <Field label="目标 URL" required hint="只作为范围描述；当前阶段不会访问目标站点执行测试。">
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
                                        <Field label="允许域名（每行一个）" required hint="例如 jsonplaceholder.typicode.com，不需要写 https://。">
                                            <Textarea className="min-h-24 font-mono" value={form.allowed_domains} onChange={(event) => updateForm("allowed_domains", event.target.value)} />
                                        </Field>
                                        <Field label="允许路径（每行一个）" required hint="例如 /posts；后续阶段会用它限制执行范围。">
                                            <Textarea className="min-h-24 font-mono" value={form.allowed_paths} onChange={(event) => updateForm("allowed_paths", event.target.value)} />
                                        </Field>
                                        <Field label="禁止动作（每行一个）" hint="删除、支付、短信、邮件等动作默认应放在这里。">
                                            <Textarea className="min-h-24 font-mono" value={form.forbidden_actions} onChange={(event) => updateForm("forbidden_actions", event.target.value)} />
                                        </Field>
                                        <Field label="需确认动作（每行一个）" hint="例如 POST /posts；当前阶段只记录确认要求，不执行动作。">
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

                                    <InlineNotice>
                                        生成 AI 计划只会创建候选流程、API 候选和风险项，不会执行任何测试请求。
                                    </InlineNotice>

                                    <div className="flex flex-wrap gap-3">
                                        <div>
                                            <Button onClick={() => void handleSaveCampaign()} disabled={isSaving} className="gap-2">
                                                <Save className="h-4 w-4" />
                                                {isSaving ? "保存中..." : "保存 Campaign 草稿"}
                                            </Button>
                                            <ActionHint>{saveCampaignHint}</ActionHint>
                                        </div>
                                        <div>
                                            <Button variant="secondary" onClick={() => void handleGeneratePlan()} disabled={isSaving || isGeneratingPlan} className="gap-2">
                                                <Sparkles className="h-4 w-4" />
                                                {isGeneratingPlan ? "正在生成计划..." : "生成 AI 计划"}
                                            </Button>
                                            <ActionHint>{generatePlanHint}</ActionHint>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="plan">
                            <div className="space-y-4">
                                {!currentPlan ? (
                                    <EmptyState title="AI 计划尚未生成" description="请先保存 Campaign 草稿，再点击“生成 AI 计划”。该操作不会执行测试。" />
                                ) : (
                                    <>
                                        <Card className="border-sky-100 bg-white/90">
                                            <CardHeader>
                                                <CardTitle className="flex items-center justify-between gap-3">
                                                    <span>计划概览</span>
                                                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">v{currentPlan.version} · {currentPlan.status}</Badge>
                                                </CardTitle>
                                            </CardHeader>
                                            <CardContent className="space-y-4">
                                                <div className="grid gap-3 md:grid-cols-4">
                                                    <StatusMetric label="API 候选" value={currentPlan.api_candidates.length} />
                                                    <StatusMetric label="风险项" value={currentPlan.risk_items.length} />
                                                    <StatusMetric label="人工复核项" value={currentPlan.manual_review_items.length} />
                                                    <StatusMetric label="UI Flow" value={Array.isArray(currentPlan.ui_flows) ? currentPlan.ui_flows.length : "-"} />
                                                </div>
                                                <div className="grid gap-4 md:grid-cols-2">
                                                    <JsonPreview data={currentPlan.summary} />
                                                    <JsonPreview data={currentPlan.coverage_summary} />
                                                </div>
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
                                        <EmptyState title="暂无可复核计划" description="请先生成 AI 计划，再处理写操作、条件允许和风险项。" />
                                    ) : currentPlan.manual_review_items.length === 0 ? (
                                        <EmptyState title="暂无待复核项" description="当前计划没有需要人工确认的候选项，可以进入资产草稿预览。" />
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
                                                        <Field label="复核选择" hint={getReviewChoiceDescription(draft.choice)}>
                                                            <Select value={draft.choice || undefined} onValueChange={(value) => updateReviewDraft(item.id, "choice", value)}>
                                                                <SelectTrigger className="w-full"><SelectValue placeholder="请选择" /></SelectTrigger>
                                                                <SelectContent>
                                                                    {item.available_choices.map((choice) => (
                                                                        <SelectItem key={choice} value={choice}>{choiceLabels[choice] || choice}</SelectItem>
                                                                    ))}
                                                                </SelectContent>
                                                            </Select>
                                                        </Field>
                                                        <Field label="备注" hint="可记录授权来源、限制或跳过原因。">
                                                            <Input value={draft.comment} onChange={(event) => updateReviewDraft(item.id, "comment", event.target.value)} />
                                                        </Field>
                                                        <div>
                                                            <Button onClick={() => void handleSaveReview(item)} disabled={isSavingReview === item.id || !draft.choice} className="gap-2">
                                                                <Save className="h-4 w-4" />
                                                                {isSavingReview === item.id ? "保存中..." : item.choice !== "pending" ? "更新复核选择" : "保存复核选择"}
                                                            </Button>
                                                            <ActionHint>{!draft.choice ? "请先选择复核结论。" : isSavingReview === item.id ? "正在保存该项复核。" : undefined}</ActionHint>
                                                        </div>
                                                    </div>
                                                    <InlineNotice tone="warning">
                                                        保存未来执行意向只表示该项未来可进入 Phase 3 执行前确认页；Phase 2 不触发测试执行。
                                                    </InlineNotice>
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
                                    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-sky-100 bg-sky-50 p-4 text-sm text-sky-800">
                                        <span>草稿可在明确确认后保存为正式 API Auto / Visual UI 资产；保存动作不会执行测试。</span>
                                        <div className="flex flex-wrap gap-3">
                                            <div>
                                                <Button onClick={() => void handleGenerateAssetDrafts()} disabled={isGeneratingDrafts || !currentPlan} className="gap-2">
                                                    <Database className="h-4 w-4" />
                                                    {isGeneratingDrafts ? "正在生成草稿..." : displayedApiDrafts.length || displayedVisualDrafts.length ? "重新生成草稿预览" : "生成资产草稿预览"}
                                                </Button>
                                                <ActionHint>{generateDraftHint}</ActionHint>
                                            </div>
                                            <div>
                                                <Button variant="secondary" onClick={() => void handlePromoteDrafts()} disabled={isPromotingDrafts || selectedDraftIds.length === 0} className="gap-2">
                                                    <Save className="h-4 w-4" />
                                                    {isPromotingDrafts ? "正在保存..." : `保存为正式资产${selectedDraftIds.length ? `（${selectedDraftIds.length}）` : ""}`}
                                                </Button>
                                                <ActionHint>{promoteHint}</ActionHint>
                                            </div>
                                        </div>
                                    </div>

                                    {!displayedApiDrafts.length && !displayedVisualDrafts.length && !assetDrafts ? (
                                        <EmptyState title="资产草稿尚未生成" description="生成后将在这里展示 API Case IR v2、Visual UI 草稿和跳过项。" />
                                    ) : (
                                        <div className="space-y-4">
                                            <div className="grid gap-3 md:grid-cols-3">
                                                <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                                                    <div className="text-xs text-slate-500">API Case IR v2</div>
                                                    <div className="mt-1 text-2xl font-bold text-slate-900">{displayedApiDrafts.length}</div>
                                                </div>
                                                <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                                                    <div className="text-xs text-slate-500">Visual UI 草稿</div>
                                                    <div className="mt-1 text-2xl font-bold text-slate-900">{displayedVisualDrafts.length}</div>
                                                </div>
                                                <div className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                                                    <div className="text-xs text-slate-500">跳过项</div>
                                                    <div className="mt-1 text-2xl font-bold text-slate-900">{assetDrafts?.skipped_items.length || 0}</div>
                                                </div>
                                            </div>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">可保存草稿</CardTitle></CardHeader>
                                                <CardContent className="space-y-3">
                                                    {displayedDraftRows.length === 0 ? (
                                                        <EmptyState title="缺少完整草稿行" description="请重新生成资产草稿预览，以获取可保存的 draft id。" />
                                                    ) : displayedDraftRows.map((draft) => {
                                                        const promotion = promotionByDraftId.get(draft.id);
                                                        const checked = selectedDraftIds.includes(draft.id);
                                                        const summary = getDraftPayloadSummary(draft);
                                                        const statusLabel = promotion ? "已保存" : draft.skipped_reason ? "不可保存" : "可保存";
                                                        return (
                                                            <div key={draft.id} className="rounded-xl border border-slate-200 bg-white p-4 text-sm">
                                                                <div className="flex flex-wrap items-start justify-between gap-3">
                                                                    <label className="flex min-w-0 flex-1 cursor-pointer items-start gap-3">
                                                                        <input
                                                                            type="checkbox"
                                                                            aria-label={`选择草稿 ${draft.id}，类型 ${draft.asset_type}`}
                                                                            className="mt-1 h-4 w-4 rounded border-slate-300"
                                                                            checked={checked}
                                                                            disabled={Boolean(promotion) || Boolean(draft.skipped_reason)}
                                                                            onChange={() => handleToggleDraft(draft.id)}
                                                                        />
                                                                        <div className="min-w-0 space-y-2">
                                                                            <div className="flex flex-wrap items-center gap-2">
                                                                                <Badge variant="secondary">{draft.asset_type}</Badge>
                                                                                {renderPolicyBadge(draft.policy)}
                                                                                {draft.risk_level ? <Badge variant="outline">风险：{draft.risk_level}</Badge> : null}
                                                                                <Badge variant="outline" className={promotion ? "border-emerald-200 bg-emerald-50 text-emerald-700" : draft.skipped_reason ? "border-red-200 bg-red-50 text-red-700" : "border-sky-200 bg-sky-50 text-sky-700"}>{statusLabel}</Badge>
                                                                                {promotion ? <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">正式资产：{promotion.generated_asset_id}</Badge> : null}
                                                                            </div>
                                                                            <div>
                                                                                <div className="font-semibold text-slate-900">{summary.title}</div>
                                                                                <div className="mt-1 text-xs text-slate-500">{summary.line}</div>
                                                                            </div>
                                                                            <div className="font-mono text-xs text-slate-500">{draft.id}</div>
                                                                            <div className="text-xs text-slate-500">来源：{draft.source_type} / {draft.source_item_id}</div>
                                                                            {draft.skipped_reason ? <div className="text-xs text-red-600">不可保存原因：{draft.skipped_reason}</div> : null}
                                                                        </div>
                                                                    </label>
                                                                </div>
                                                                <div className="mt-3">
                                                                    <JsonPreview data={draft.draft_payload} />
                                                                </div>
                                                            </div>
                                                        );
                                                    })}
                                                </CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">保存结果</CardTitle></CardHeader>
                                                <CardContent className="space-y-3">
                                                    <div className="grid gap-3 md:grid-cols-5">
                                                        <StatusMetric label="新建" value={promotionResult?.promoted.length || 0} />
                                                        <StatusMetric label="重复" value={promotionResult?.duplicates.length || 0} />
                                                        <StatusMetric label="跳过" value={promotionResult?.skipped.length || 0} />
                                                        <StatusMetric label="失败" value={promotionResult?.failed.length || 0} />
                                                        <StatusMetric label="创建执行" value={promotionResult?.execution_created ? "是" : "否"} hint="Phase 2 应为否" />
                                                    </div>
                                                    <JsonPreview data={promotionResult || { promoted: [], duplicates: [], skipped: [], failed: [], execution_created: false }} />
                                                </CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">API Case IR v2 草稿</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={displayedApiDrafts} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">Visual UI 草稿</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={displayedVisualDrafts} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">跳过项</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts?.skipped_items || []} /></CardContent>
                                            </Card>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">草稿元信息</CardTitle></CardHeader>
                                                <CardContent><JsonPreview data={assetDrafts?.asset_drafts || currentPlan?.asset_drafts || {}} /></CardContent>
                                            </Card>
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="execution">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <PlayCircle className="h-5 w-5 text-emerald-600" />
                                        执行前确认
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {!activeCampaign || !currentPlan ? (
                                        <EmptyState title="暂无可执行计划" description="请先完成 Campaign、AI 计划、人工复核和正式资产保存。" />
                                    ) : (
                                        <>
                                            <InlineNotice tone="warning" title="Phase 3 会创建 Execution 并进入调度">
                                                请选择已保存的 API / Visual UI 资产，并确认只在允许域名和路径内执行。后端会再次校验策略、复核选择和安全边界。
                                            </InlineNotice>
                                            <div className="grid gap-3 md:grid-cols-4">
                                                <StatusMetric label="允许域名" value={splitLines(form.allowed_domains).length} hint={splitLines(form.allowed_domains).join(", ") || "-"} />
                                                <StatusMetric label="允许路径" value={splitLines(form.allowed_paths).length} hint={splitLines(form.allowed_paths).join(", ") || "-"} />
                                                <StatusMetric label="环境安全" value={form.environment_safety || "-"} />
                                                <StatusMetric label="写入策略" value={form.write_policy || "-"} />
                                            </div>
                                            {executablePromotions.length === 0 ? (
                                                <EmptyState title="还没有已保存资产" description="先在“资产草稿”阶段保存 API 或 Visual UI 草稿；Phase 2 保存完成后仍不会执行。" />
                                            ) : (
                                                <div className="space-y-3">
                                                    {executablePromotions.map((promotion) => {
                                                        const checked = selectedPromotionIds.includes(promotion.id);
                                                        const metadata = promotion.promotion_metadata || {};
                                                        const policy = getText(metadata.policy, "allowed");
                                                        return (
                                                            <label key={promotion.id} className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-white p-4 text-sm">
                                                                <input
                                                                    type="checkbox"
                                                                    aria-label={`选择执行资产 ${promotion.id}，类型 ${promotion.generated_asset_type}`}
                                                                    className="mt-1 h-4 w-4 rounded border-slate-300"
                                                                    checked={checked}
                                                                    onChange={() => handleTogglePromotion(promotion.id)}
                                                                />
                                                                <div className="min-w-0 flex-1 space-y-2">
                                                                    <div className="flex flex-wrap items-center gap-2">
                                                                        <Badge variant="secondary">{promotion.generated_asset_type}</Badge>
                                                                        <Badge variant="outline" className="border-emerald-200 bg-emerald-50 text-emerald-700">{promotion.status}</Badge>
                                                                        {renderPolicyBadge(policy)}
                                                                    </div>
                                                                    <div className="font-semibold text-slate-900">正式资产：{promotion.generated_asset_id}</div>
                                                                    <div className="font-mono text-xs text-slate-500">Promotion：{promotion.id}</div>
                                                                    <div className="text-xs text-slate-500">Draft：{promotion.asset_draft_id} · 保存时间：{formatDate(promotion.created_at)}</div>
                                                                </div>
                                                            </label>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                            <label className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                                                <input
                                                    type="checkbox"
                                                    aria-label="确认已授权执行所选 Smart Scan 资产"
                                                    className="mt-1 h-4 w-4 rounded border-amber-300"
                                                    checked={executionAuthorizationChecked}
                                                    onChange={(event) => setExecutionAuthorizationChecked(event.target.checked)}
                                                />
                                                <span>
                                                    我确认已获得授权，只在本 Campaign 的允许域名和路径内执行所选资产，并理解写操作、表单提交和 UI 自动化可能访问目标系统。
                                                </span>
                                            </label>
                                            <div>
                                                <Button
                                                    onClick={() => void handleConfirmExecution()}
                                                    disabled={isConfirmingExecution || selectedPromotionIds.length === 0 || !executionAuthorizationChecked}
                                                    className="gap-2"
                                                >
                                                    <PlayCircle className="h-4 w-4" />
                                                    {isConfirmingExecution ? "正在创建执行..." : `确认授权并创建执行${selectedPromotionIds.length ? `（${selectedPromotionIds.length}）` : ""}`}
                                                </Button>
                                                <ActionHint>{confirmExecutionHint}</ActionHint>
                                            </div>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader><CardTitle className="text-base">执行创建结果</CardTitle></CardHeader>
                                                <CardContent className="space-y-3">
                                                    <div className="grid gap-3 md:grid-cols-4">
                                                        <StatusMetric label="Execution ID" value={executionResult?.execution_id || "-"} />
                                                        <StatusMetric label="状态" value={executionResult?.status || "-"} />
                                                        <StatusMetric label="总用例" value={executionResult?.total_cases || 0} />
                                                        <StatusMetric label="Visual 动态载荷" value={executionResult?.dynamic_payload_count || 0} />
                                                    </div>
                                                    {executionResult ? (
                                                        <div className="flex flex-wrap gap-3">
                                                            <Button variant="outline" asChild>
                                                                <a href="/executions">查看执行列表</a>
                                                            </Button>
                                                            <Button variant="outline" asChild>
                                                                <a href={executionResult.dashboard_url}>打开本次执行</a>
                                                            </Button>
                                                        </div>
                                                    ) : null}
                                                    <JsonPreview data={executionResult || { execution_created: false, selected_promotions: [], tc_ids: [], skipped: [] }} />
                                                </CardContent>
                                            </Card>
                                        </>
                                    )}
                                </CardContent>
                            </Card>
                        </TabsContent>

                        <TabsContent value="results">
                            <Card className="border-sky-100 bg-white/90 shadow-lg shadow-sky-100/50">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2">
                                        <ShieldCheck className="h-5 w-5 text-emerald-600" />
                                        结果闭环
                                    </CardTitle>
                                </CardHeader>
                                <CardContent className="space-y-4">
                                    {!activeCampaign || !currentPlan ? (
                                        <EmptyState title="暂无可回流结果" description="请先选择 Campaign 并完成 AI 计划生成。" />
                                    ) : (
                                        <>
                                            <InlineNotice tone="info" title="Phase 4 汇总执行结果并沉淀报告">
                                                这里仅回流本 Campaign / Plan 通过 Phase 3 授权创建的 Execution；重新执行仍需回到执行确认页重新授权。
                                            </InlineNotice>
                                            <div className="flex flex-wrap gap-3">
                                                <Button
                                                    variant="outline"
                                                    onClick={() => void loadExecutionSummary(activeCampaign.id, currentPlan.plan_id)}
                                                    disabled={isLoadingExecutionSummary}
                                                    className="gap-2"
                                                >
                                                    <RefreshCw className="h-4 w-4" />
                                                    {isLoadingExecutionSummary ? "刷新中..." : "刷新结果"}
                                                </Button>
                                                <Button
                                                    onClick={() => void loadSmartScanReport(activeCampaign.id, currentPlan.plan_id)}
                                                    disabled={isLoadingReport}
                                                    className="gap-2"
                                                >
                                                    <FileJson className="h-4 w-4" />
                                                    {isLoadingReport ? "生成中..." : "生成 / 刷新报告"}
                                                </Button>
                                                <Button variant="secondary" onClick={() => setActiveTab("execution")}>
                                                    回到执行确认重新授权
                                                </Button>
                                            </div>
                                            <div className="grid gap-3 md:grid-cols-4">
                                                <StatusMetric label="执行次数" value={executionSummary?.total_executions || 0} />
                                                <StatusMetric label="最近状态" value={executionSummary?.latest_status || "-"} />
                                                <StatusMetric
                                                    label="最近 Execution"
                                                    value={executionSummary?.latest_execution_id || "-"}
                                                    hint={executionSummary?.latest_updated_at ? formatDate(executionSummary.latest_updated_at) : undefined}
                                                />
                                                <StatusMetric
                                                    label="最近通过率"
                                                    value={executionSummary?.executions[0] ? `${Math.round(executionSummary.executions[0].pass_rate * 100)}%` : "-"}
                                                    hint={executionSummary?.executions[0] ? `${executionSummary.executions[0].passed_cases}/${executionSummary.executions[0].total_cases}` : undefined}
                                                />
                                            </div>
                                            {!executionSummary || executionSummary.executions.length === 0 ? (
                                                <EmptyState title="还没有执行记录" description="完成 Phase 3 授权并创建 Execution 后，这里会显示执行历史和报告入口。" />
                                            ) : (
                                                <div className="space-y-3">
                                                    {executionSummary.executions.map((execution) => (
                                                        <Card key={execution.execution_id} className="border-slate-200 bg-white py-4">
                                                            <CardContent className="space-y-3 px-4">
                                                                <div className="flex flex-wrap items-center justify-between gap-3">
                                                                    <div>
                                                                        <div className="font-mono text-sm font-semibold text-slate-900">{execution.execution_id}</div>
                                                                        <div className="text-xs text-slate-500">创建：{formatDate(execution.created_at)} · 更新：{formatDate(execution.updated_at)}</div>
                                                                    </div>
                                                                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">{execution.status}</Badge>
                                                                </div>
                                                                <div className="grid gap-3 md:grid-cols-5">
                                                                    <StatusMetric label="总用例" value={execution.total_cases} />
                                                                    <StatusMetric label="通过" value={execution.passed_cases} />
                                                                    <StatusMetric label="失败" value={execution.failed_cases} />
                                                                    <StatusMetric label="通过率" value={`${Math.round(execution.pass_rate * 100)}%`} />
                                                                    <StatusMetric label="Visual 动态载荷" value={execution.dynamic_payload_count} hint={execution.duration_seconds ? `${execution.duration_seconds}s` : undefined} />
                                                                </div>
                                                            </CardContent>
                                                        </Card>
                                                    ))}
                                                </div>
                                            )}
                                            <div className="grid gap-4 xl:grid-cols-2">
                                                <Card className="border-slate-200 bg-white py-4">
                                                    <CardHeader><CardTitle className="text-base">失败归因</CardTitle></CardHeader>
                                                    <CardContent>
                                                        <JsonPreview data={executionSummary?.failure_categories || []} />
                                                    </CardContent>
                                                </Card>
                                                <Card className="border-slate-200 bg-white py-4">
                                                    <CardHeader><CardTitle className="text-base">结果分布</CardTitle></CardHeader>
                                                    <CardContent>
                                                        <JsonPreview data={executionSummary?.result_breakdown || { api: {}, visual_ui: {} }} />
                                                    </CardContent>
                                                </Card>
                                            </div>
                                            <Card className="border-slate-200 bg-white py-4">
                                                <CardHeader>
                                                    <CardTitle className="flex flex-wrap items-center justify-between gap-3 text-base">
                                                        <span>Smart Scan 报告</span>
                                                        <span className="flex flex-wrap gap-2">
                                                            <Button variant="outline" size="sm" onClick={() => void handleCopyReportMarkdown()} disabled={!smartScanReport?.markdown}>复制 Markdown</Button>
                                                            <Button variant="outline" size="sm" onClick={() => void handleCopyReportJson()} disabled={!smartScanReport}>复制 JSON</Button>
                                                        </span>
                                                    </CardTitle>
                                                </CardHeader>
                                                <CardContent className="space-y-3">
                                                    {smartScanReport ? (
                                                        <>
                                                            <div className="text-xs text-slate-500">生成时间：{formatDate(smartScanReport.generated_at)}</div>
                                                            <pre className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-relaxed text-slate-100">
                                                                {smartScanReport.markdown}
                                                            </pre>
                                                        </>
                                                    ) : (
                                                        <EmptyState title="报告尚未生成" description="点击“生成 / 刷新报告”后，会沉淀 Campaign、计划、复核、资产和执行结果。" />
                                                    )}
                                                </CardContent>
                                            </Card>
                                        </>
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
