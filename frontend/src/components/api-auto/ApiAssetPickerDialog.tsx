"use client"

import React, { useCallback, useEffect, useState } from "react";
import { Database, Loader2, PlusCircle, Search } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { apiAssetService, ApiAsset } from "@/services/apiAssetService";
import type { ApiStep } from "@/services/apiAutoService";

interface ApiAssetPickerDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSelectStep: (step: ApiStep, asset: ApiAsset) => void;
}

const METHODS = ["ALL", "GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"];

const METHOD_STYLES: Record<string, string> = {
    GET: "border-blue-200 bg-blue-50 text-blue-700",
    POST: "border-emerald-200 bg-emerald-50 text-emerald-700",
    PUT: "border-amber-200 bg-amber-50 text-amber-700",
    PATCH: "border-violet-200 bg-violet-50 text-violet-700",
    DELETE: "border-rose-200 bg-rose-50 text-rose-700",
    HEAD: "border-slate-200 bg-slate-50 text-slate-700",
    OPTIONS: "border-cyan-200 bg-cyan-50 text-cyan-700",
};

export function ApiAssetPickerDialog({ open, onOpenChange, onSelectStep }: ApiAssetPickerDialogProps) {
    const [assets, setAssets] = useState<ApiAsset[]>([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [keywordInput, setKeywordInput] = useState("");
    const [keyword, setKeyword] = useState("");
    const [method, setMethod] = useState("ALL");
    const [isLoading, setIsLoading] = useState(false);
    const [addingAssetId, setAddingAssetId] = useState<string | null>(null);

    const pageSize = 10;
    const totalPages = Math.max(1, Math.ceil(total / pageSize));

    const loadAssets = useCallback(async () => {
        if (!open) return;
        setIsLoading(true);
        try {
            const res = await apiAssetService.listAssets({
                page,
                pageSize,
                keyword,
                method,
            });
            setAssets(res.data.items || []);
            setTotal(res.data.total || 0);
        } catch (err: unknown) {
            toast.error("加载接口资产失败 (Failed to load API assets)", {
                description: (err as { message?: string }).message,
            });
        } finally {
            setIsLoading(false);
        }
    }, [keyword, method, open, page]);

    useEffect(() => {
        void loadAssets();
    }, [loadAssets]);

    const handleSearch = () => {
        setPage(1);
        setKeyword(keywordInput.trim());
    };

    const handleMethodChange = (value: string) => {
        setPage(1);
        setMethod(value);
    };

    const handleAddAsset = async (asset: ApiAsset) => {
        setAddingAssetId(asset.id);
        try {
            const res = await apiAssetService.getApiIrStep(asset.id);
            onSelectStep(res.data.step, asset);
            onOpenChange(false);
        } catch (err: unknown) {
            toast.error("生成 API step 失败 (Failed to generate API step)", {
                description: (err as { message?: string }).message,
            });
        } finally {
            setAddingAssetId(null);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-4xl border-sky-100 bg-white text-slate-900 shadow-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2 text-slate-950">
                        <Database className="h-5 w-5 text-sky-600" />
                        从接口资产库添加 API Step
                    </DialogTitle>
                    <DialogDescription>
                        选择一个接口资产，系统会生成 API Case IR v2 step 并追加到当前 API 集合。
                    </DialogDescription>
                </DialogHeader>

                <div className="flex flex-col gap-4">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center">
                        <div className="flex flex-1 items-center gap-2">
                            <Input
                                value={keywordInput}
                                onChange={(e) => setKeywordInput(e.target.value)}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") handleSearch();
                                }}
                                placeholder="搜索路径、名称、operationId、标签..."
                                className="bg-white/85 border-sky-200 text-slate-900 placeholder:text-slate-400"
                            />
                            <Button variant="outline" onClick={handleSearch} className="border-sky-200 bg-white text-slate-700 hover:bg-sky-50">
                                <Search className="h-4 w-4 mr-1" />
                                搜索
                            </Button>
                        </div>
                        <Select value={method} onValueChange={handleMethodChange}>
                            <SelectTrigger className="w-full md:w-40 bg-white/85 border-sky-200 text-slate-800">
                                <SelectValue placeholder="Method" />
                            </SelectTrigger>
                            <SelectContent className="bg-white border-sky-100 text-slate-800 shadow-xl">
                                {METHODS.map((item) => (
                                    <SelectItem key={item} value={item}>{item === "ALL" ? "全部方法" : item}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="min-h-[360px] rounded-2xl border border-sky-100 bg-sky-50/40 p-3">
                        {isLoading ? (
                            <div className="flex h-[330px] items-center justify-center text-slate-500">
                                <Loader2 className="h-5 w-5 mr-2 animate-spin text-sky-500" />
                                加载接口资产中...
                            </div>
                        ) : assets.length === 0 ? (
                            <div className="flex h-[330px] flex-col items-center justify-center text-center text-slate-500">
                                <Database className="h-10 w-10 mb-3 text-sky-300" />
                                <p className="font-medium text-slate-700">暂无可用接口资产</p>
                                <p className="mt-1 text-sm">请先通过 OpenAPI/Swagger 导入或手工维护接口资产。</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {assets.map((asset) => (
                                    <div
                                        key={asset.id}
                                        className="rounded-2xl border border-white/80 bg-white/90 p-4 shadow-sm transition hover:border-sky-200 hover:shadow-md"
                                    >
                                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                            <div className="min-w-0 flex-1">
                                                <div className="flex flex-wrap items-center gap-2">
                                                    <Badge variant="outline" className={METHOD_STYLES[asset.method] || "border-slate-200 bg-slate-50 text-slate-700"}>
                                                        {asset.method}
                                                    </Badge>
                                                    <span className="font-mono text-sm font-semibold text-slate-900">{asset.path}</span>
                                                    {asset.deprecated && <Badge variant="outline" className="border-amber-200 bg-amber-50 text-amber-700">Deprecated</Badge>}
                                                </div>
                                                <div className="mt-2 text-sm font-medium text-slate-800">
                                                    {asset.summary || asset.name || asset.operation_id || asset.asset_key}
                                                </div>
                                                <div className="mt-1 text-xs text-slate-500">
                                                    来源: {asset.source_name}{asset.operation_id ? ` · ${asset.operation_id}` : ""}
                                                </div>
                                                {asset.tags?.length > 0 && (
                                                    <div className="mt-2 flex flex-wrap gap-1">
                                                        {asset.tags.slice(0, 5).map((tag) => (
                                                            <Badge key={tag} variant="secondary" className="bg-slate-100 text-slate-600">
                                                                {tag}
                                                            </Badge>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                            <Button
                                                size="sm"
                                                onClick={() => void handleAddAsset(asset)}
                                                disabled={addingAssetId === asset.id}
                                                className="bg-gradient-to-r from-sky-500 via-blue-500 to-violet-500 text-white shadow-lg shadow-sky-500/20 hover:from-sky-600 hover:via-blue-600 hover:to-violet-600"
                                            >
                                                {addingAssetId === asset.id ? (
                                                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                                                ) : (
                                                    <PlusCircle className="h-4 w-4 mr-1" />
                                                )}
                                                添加
                                            </Button>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                <DialogFooter className="items-center justify-between sm:justify-between">
                    <div className="text-sm text-slate-500">
                        共 {total} 个资产，第 {page} / {totalPages} 页
                    </div>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            onClick={() => setPage((current) => Math.max(1, current - 1))}
                            disabled={page <= 1 || isLoading}
                            className="border-sky-200 bg-white text-slate-700 hover:bg-sky-50"
                        >
                            上一页
                        </Button>
                        <Button
                            variant="outline"
                            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
                            disabled={page >= totalPages || isLoading}
                            className="border-sky-200 bg-white text-slate-700 hover:bg-sky-50"
                        >
                            下一页
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
