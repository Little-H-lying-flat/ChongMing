"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Play, Activity, Settings, Database, Server, Zap, Brain } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { OmniParserStatus } from "./OmniParserStatus";

const navItems = [
    { name: "总览大盘", href: "/", icon: LayoutDashboard },
    { name: "需求解析", href: "/design", icon: Activity },
    { name: "调度大盘", href: "/executions", icon: Play },
    { name: "视觉 UI", href: "/visual-ui", icon: Server },
    { name: "接口自动化", href: "/api-auto", icon: Database },
    { name: "性能压测", href: "/turbo", icon: Zap },
    { name: "模型治理", href: "/smart-ops", icon: Brain },
    { name: "系统设置", href: "/settings", icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();

    return (
        <div className="flex flex-col h-screen w-64 bg-slate-900 text-white border-r border-slate-800">
            <div className="p-6 border-b border-slate-800">
                <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                    ChongMing
                </h1>
                <p className="text-xs text-slate-400 mt-1">Intelligent Test Platform</p>
            </div>

            <nav className="flex-1 p-4 space-y-2">
                {navItems.map((item) => {
                    const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
                    return (
                        <Link key={item.href} href={item.href}>
                            <Button
                                variant={isActive ? "secondary" : "ghost"}
                                className={cn(
                                    "w-full justify-start gap-3",
                                    isActive ? "bg-slate-800 text-blue-400" : "text-slate-400 hover:text-white hover:bg-slate-800"
                                )}
                            >
                                <item.icon className="w-5 h-5" />
                                {item.name}
                            </Button>
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 border-t border-slate-800 space-y-4">
                <OmniParserStatus />
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center font-bold">
                        CM
                    </div>
                    <div>
                        <p className="text-sm font-medium">Admin User</p>
                        <p className="text-xs text-slate-500">admin@chongming.ai</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
