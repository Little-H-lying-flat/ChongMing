"use client";

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, Play, Server, Brain, Settings, Code2, FileText, Gauge, Flame, ShieldAlert, Rocket } from 'lucide-react'
import { Button } from './ui/button'

const Sidebar = () => {
  const pathname = usePathname()

  const navItems = [
    { name: '总览大盘 (Overview)', path: '/', icon: LayoutDashboard },
    { name: '调度大盘 (Executions)', path: '/executions', icon: Play },
    { name: '视觉UI (Visual UI)', path: '/visual-ui', icon: Server },
    { name: '接口工厂 (API Auto)', path: '/api-auto', icon: Code2 },
    { name: '需求设计 (Design)', path: '/design', icon: FileText },
    { name: '性能压测 (Performance)', path: '/performance', icon: Gauge },
    { name: '凤凰仓库 (Phoenix)', path: '/phoenix', icon: Flame },
    { name: '智能运维 (Smart Ops)', path: '/smart-ops', icon: ShieldAlert },
    { name: '模型治理 (Model Config)', path: '/model-config', icon: Brain },
    { name: '系统设置 (Settings)', path: '/settings', icon: Settings },
    { name: 'Turbo 占位 (Turbo)', path: '/turbo', icon: Rocket },
  ]

  return (
    <div className="flex h-screen w-64 flex-col border-r border-sky-100/80 bg-white/75 text-slate-900 shadow-[12px_0_40px_-28px_rgba(14,165,233,0.5)] backdrop-blur-xl">
      <div className="border-b border-sky-100 p-6">
        <h1 className="bg-gradient-to-r from-sky-600 via-blue-600 to-violet-600 bg-clip-text text-2xl font-bold text-transparent">ChongMing</h1>
        <p className="mt-1 text-xs text-slate-500">智能测试平台 (Intelligent Test Platform)</p>
      </div>

      <nav className="flex-1 overflow-y-auto p-4 space-y-2 geek-scrollbar">
        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = pathname === item.path
          return (
            <Link key={item.path} href={item.path}>
              <Button
                variant={isActive ? 'secondary' : 'ghost'}
                className={`w-full justify-start gap-3 rounded-xl ${isActive
                  ? 'border border-sky-200 bg-gradient-to-r from-sky-100 via-white to-violet-100 text-sky-800 shadow-sm'
                  : 'text-slate-600 hover:bg-sky-50 hover:text-sky-800'
                  }`}
              >
                <Icon className="w-5 h-5" />
                {item.name}
              </Button>
            </Link>
          )
        })}
      </nav>

      <div className="space-y-4 border-t border-sky-100 p-4">
        {/* User Info */}
        <div className="flex items-center gap-3 rounded-2xl border border-white/70 bg-white/60 p-3 shadow-sm">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-500 font-bold text-white shadow-lg shadow-sky-500/20">
            CM
          </div>
          <div>
            <p className="text-sm font-medium text-slate-900">管理员 (Admin User)</p>
            <p className="text-xs text-slate-500">admin@chongming.ai</p>
          </div>
        </div>
      </div>
    </div>
  )
}

export { Sidebar }
