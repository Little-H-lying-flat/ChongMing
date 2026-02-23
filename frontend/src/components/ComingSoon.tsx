import { Rocket } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

interface ComingSoonProps {
    title: string;
}

export function ComingSoon({ title }: ComingSoonProps) {
    return (
        <div className="flex items-center justify-center h-full">
            <Card className="w-full max-w-md bg-slate-900 border-slate-800 text-slate-100 shadow-2xl">
                <CardContent className="flex flex-col items-center justify-center p-12 text-center space-y-6">
                    <div className="relative">
                        <div className="absolute -inset-1 rounded-full bg-blue-500/20 blur-xl animate-pulse"></div>
                        <div className="relative bg-slate-800 p-4 rounded-full border border-slate-700">
                            <Rocket className="w-12 h-12 text-blue-500" />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-cyan-300 bg-clip-text text-transparent">
                            {title}
                        </h1>
                        <p className="text-slate-400 text-sm">
                            该核心业务模块正在研发与接入中... (This module is under development...)
                        </p>
                    </div>

                    <div className="w-full h-1 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500/50 w-1/3 animate-[shimmer_2s_infinite]"></div>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
