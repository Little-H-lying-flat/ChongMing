import React from 'react';
import {
    DndContext,
    closestCenter,
    KeyboardSensor,
    PointerSensor,
    useSensor,
    useSensors,
    DragEndEvent
} from '@dnd-kit/core';
import {
    arrayMove,
    SortableContext,
    sortableKeyboardCoordinates,
    verticalListSortingStrategy,
    useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { VisualStep } from '@/services/visualUiService';
import { Trash2, GripVertical, Plus, Eye } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface StepBuilderProps {
    steps: VisualStep[];
    onChange: (steps: VisualStep[]) => void;
}

const ACTION_META: Record<VisualStep['action'], {
    label: string;
    className: string;
    helper: string;
    targetHelper: string;
    valueHelper: string;
}> = {
    GOTO: {
        label: 'GOTO',
        className: 'border-amber-200 bg-amber-50 text-amber-700',
        helper: '打开目标页面。 (Navigate to a URL.)',
        targetHelper: 'GOTO 不需要目标元素描述。 (No target element is needed.)',
        valueHelper: '填写完整 URL；留空时可使用 Base URL。 (Use a full URL or Base URL.)',
    },
    CLICK: {
        label: 'CLICK',
        className: 'border-fuchsia-200 bg-fuchsia-50 text-fuchsia-700',
        helper: '点击一个可见元素。 (Click a visible element.)',
        targetHelper: '描述要点击的按钮、链接或区域。 (Describe the element to click.)',
        valueHelper: 'CLICK 不需要输入值。 (No value is needed.)',
    },
    TYPE: {
        label: 'TYPE',
        className: 'border-cyan-200 bg-cyan-50 text-cyan-700',
        helper: '向输入框填写文本。 (Type text into a field.)',
        targetHelper: '描述输入框或表单字段。 (Describe the field.)',
        valueHelper: '填写要输入的文本。 (Text to type.)',
    },
    WAIT: {
        label: 'WAIT',
        className: 'border-blue-200 bg-blue-50 text-blue-700',
        helper: '等待页面稳定或条件出现。 (Wait for stability or a condition.)',
        targetHelper: '描述等待条件或秒数。 (Describe condition or seconds.)',
        valueHelper: 'WAIT 通常不需要输入值。 (Usually no value is needed.)',
    },
    ASSERT: {
        label: 'ASSERT',
        className: 'border-emerald-200 bg-emerald-50 text-emerald-700',
        helper: '验证页面状态或文字。 (Assert page state or text.)',
        targetHelper: '描述要验证的区域。 (Describe the area to check.)',
        valueHelper: '填写期望看到的文字或状态。 (Expected text or state.)',
    },
    SCROLL: {
        label: 'SCROLL',
        className: 'border-indigo-200 bg-indigo-50 text-indigo-700',
        helper: '滚动页面或区域。 (Scroll the page or area.)',
        targetHelper: '描述滚动方向或目标区域。 (Describe direction or area.)',
        valueHelper: 'SCROLL 通常不需要输入值。 (Usually no value is needed.)',
    },
};

const ACTION_OPTIONS = [
    { value: 'GOTO', label: '导航 GOTO (Navigate)' },
    { value: 'CLICK', label: '点击 CLICK (Click)' },
    { value: 'TYPE', label: '输入 TYPE (Type)' },
    { value: 'WAIT', label: '等待 WAIT (Wait)' },
    { value: 'ASSERT', label: '断言 ASSERT (Assert)' },
    { value: 'SCROLL', label: '滚动 SCROLL (Scroll)' },
] as const;

// --- Sortable Item Component ---
function SortableStepItem({
    step,
    index,
    onUpdate,
    onRemove
}: {
    step: VisualStep;
    index: number;
    onUpdate: (id: string, updates: Partial<VisualStep>) => void;
    onRemove: (id: string) => void;
}) {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id: step.id || String(index) });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 10 : 1,
    };
    const stepId = step.id || String(index);
    const actionMeta = ACTION_META[step.action];

    return (
        <div
            ref={setNodeRef}
            style={style}
            className={`relative mb-3 flex items-start gap-3 overflow-hidden rounded-2xl border border-sky-100 bg-white/80 p-4 shadow-sm transition-all before:absolute before:left-0 before:top-0 before:h-full before:w-1 before:bg-gradient-to-b before:from-sky-400 before:to-violet-400 hover:border-sky-200 hover:shadow-md ${isDragging ? 'opacity-80 ring-2 ring-sky-400 shadow-lg shadow-sky-200/60' : ''}`}
        >
            <button
                type="button"
                {...attributes}
                {...listeners}
                aria-label={`拖拽第 ${index + 1} 步重新排序 (Drag step ${index + 1} to reorder)`}
                title="拖拽重新排序 (Drag to reorder)"
                className="mt-2 cursor-grab rounded-md p-1 text-slate-400 hover:bg-sky-50 hover:text-sky-700 focus:outline-none focus:ring-2 focus:ring-sky-400"
            >
                <GripVertical size={18} />
            </button>

            <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-3">
                {/* Number Badge */}
                <div className="md:col-span-1 flex items-center justify-start md:justify-center">
                    <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-700">
                        #{index + 1}
                    </Badge>
                </div>

                {/* Action Select */}
                <div className="md:col-span-3 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                        <Label htmlFor={`step-${stepId}-action`} className="text-xs text-slate-700">动作 (Action)</Label>
                        <Badge variant="outline" className={actionMeta.className}>{actionMeta.label}</Badge>
                    </div>
                    <Select
                        value={step.action}
                        onValueChange={(val: string) => onUpdate(stepId, { action: val as VisualStep['action'] })}
                    >
                        <SelectTrigger id={`step-${stepId}-action`} aria-label={`第 ${index + 1} 步动作 (Step ${index + 1} action)`} className="w-full border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus:ring-sky-400">
                            <SelectValue placeholder="动作 (Action)" />
                        </SelectTrigger>
                        <SelectContent className="border-slate-200 bg-white text-slate-900 shadow-xl">
                            {ACTION_OPTIONS.map(opt => (
                                <SelectItem key={opt.value} value={opt.value} className="cursor-pointer focus:bg-sky-50 focus:text-sky-800">
                                    {opt.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <p className="text-[11px] text-slate-500">{actionMeta.helper}</p>
                </div>

                {/* Target Description */}
                <div className="md:col-span-4 space-y-1.5">
                    <Label htmlFor={`step-${stepId}-target`} className="text-xs text-slate-700">目标描述 (Target)</Label>
                    <Input
                        id={`step-${stepId}-target`}
                        aria-label={`第 ${index + 1} 步目标描述 (Step ${index + 1} target description)`}
                        placeholder={step.action === 'WAIT' ? '等待条件/秒数 (Wait condition/seconds)' : (step.action === 'GOTO' ? '说明可选 (Note (optional))' : '自然语言描述目标 (Describe target in natural language)')}
                        value={step.target_description || ''}
                        onChange={(e) => onUpdate(stepId, { target_description: e.target.value })}
                        disabled={['GOTO'].includes(step.action)}
                        className="border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus-visible:ring-sky-400 disabled:bg-slate-100 disabled:text-slate-400 disabled:opacity-70"
                    />
                    <p className="text-[11px] text-slate-500">{actionMeta.targetHelper}</p>
                </div>

                {/* Value Input */}
                <div className="md:col-span-3 space-y-1.5">
                    <Label htmlFor={`step-${stepId}-value`} className="text-xs text-slate-700">输入值 (Value)</Label>
                    <Input
                        id={`step-${stepId}-value`}
                        aria-label={`第 ${index + 1} 步输入值 (Step ${index + 1} value)`}
                        placeholder={step.action === 'GOTO' ? 'https://...' : (step.action === 'TYPE' ? '输入的文本 (Text to type)' : '断言值可选 (Assert value (optional))')}
                        value={step.value || ''}
                        onChange={(e) => onUpdate(stepId, { value: e.target.value })}
                        disabled={['CLICK', 'WAIT', 'SCROLL'].includes(step.action)}
                        className="border-sky-200 bg-white text-slate-900 placeholder:text-slate-400 focus-visible:ring-sky-400 disabled:bg-slate-100 disabled:text-slate-400 disabled:opacity-70"
                    />
                    <p className="text-[11px] text-slate-500">{actionMeta.valueHelper}</p>
                </div>

                {/* Delete Action */}
                <div className="md:col-span-1 flex items-center justify-end">
                    <Button variant="ghost" size="icon" aria-label={`删除第 ${index + 1} 步 (Delete step ${index + 1})`} className="text-rose-500 hover:bg-rose-50 hover:text-rose-700" onClick={() => onRemove(stepId)}>
                        <Trash2 size={16} />
                    </Button>
                </div>
            </div>
        </div>
    );
}

// --- Main Builder Component ---
export function StepBuilder({ steps, onChange }: StepBuilderProps) {
    const sensors = useSensors(
        useSensor(PointerSensor),
        useSensor(KeyboardSensor, {
            coordinateGetter: sortableKeyboardCoordinates,
        })
    );

    const handleDragEnd = (event: DragEndEvent) => {
        const { active, over } = event;

        if (over && active.id !== over.id) {
            const oldIndex = steps.findIndex((col) => col.id === active.id);
            const newIndex = steps.findIndex((col) => col.id === over.id);

            // Reorder and update step_index
            const newSteps = arrayMove(steps, oldIndex, newIndex).map((step, idx) => ({
                ...step,
                step_index: idx
            }));
            onChange(newSteps);
        }
    };

    const handleAddStep = () => {
        const newStep: VisualStep = {
            id: `tmp_step_${Date.now()}`,
            step_index: steps.length,
            action: 'CLICK',
            target_description: '',
            value: ''
        };
        onChange([...steps, newStep]);
    };

    const handleUpdateStep = (id: string, updates: Partial<VisualStep>) => {
        onChange(steps.map(s => s.id === id ? { ...s, ...updates } : s));
    };

    const handleRemoveStep = (id: string) => {
        const filtered = steps.filter(s => s.id !== id);
        // Re-index remaining
        const reindexed = filtered.map((step, idx) => ({ ...step, step_index: idx }));
        onChange(reindexed);
    };

    return (
        <div className="w-full">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold flex items-center gap-2 text-slate-900">
                    <span className="rounded-xl bg-sky-100 p-1.5 text-sky-700" aria-hidden="true">
                        <Eye size={18} />
                    </span>
                    自然语言步骤编排 (Natural Language Step Builder)
                </h3>
                <Button onClick={handleAddStep} size="sm" aria-label="添加视觉测试步骤 (Add visual test step)" className="gap-2 bg-gradient-to-r from-sky-500 to-violet-500 text-white shadow-lg shadow-sky-500/20 hover:from-sky-600 hover:to-violet-600">
                    <Plus size={16} /> 添加步骤 (Add Step)
                </Button>
            </div>

            {steps.length === 0 ? (
                <div className="rounded-2xl border-2 border-dashed border-sky-200 bg-white/60 py-12 text-center text-slate-500 shadow-sm">
                    <p>暂无测试步骤，请点击右上角添加。 (No test steps yet. Click top-right to add.)</p>
                </div>
            ) : (
                <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                >
                    <SortableContext
                        items={steps.map(s => s.id as string)}
                        strategy={verticalListSortingStrategy}
                    >
                        <div className="space-y-1">
                            {steps.map((step, idx) => (
                                <SortableStepItem
                                    key={step.id}
                                    step={step}
                                    index={idx}
                                    onUpdate={handleUpdateStep}
                                    onRemove={handleRemoveStep}
                                />
                            ))}
                        </div>
                    </SortableContext>
                </DndContext>
            )}
        </div>
    );
}
