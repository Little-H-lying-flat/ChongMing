import React, { useState } from 'react';
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
import { Trash2, GripVertical, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface StepBuilderProps {
    steps: VisualStep[];
    onChange: (steps: VisualStep[]) => void;
}

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

    return (
        <div
            ref={setNodeRef}
            style={style}
            className={`flex items-start gap-3 p-4 bg-slate-800/50 border border-slate-800 rounded-lg shadow-sm mb-3 ${isDragging ? 'opacity-50 ring-1 ring-indigo-500' : ''}`}
        >
            <div
                {...attributes}
                {...listeners}
                className="mt-2 cursor-grab text-slate-500 hover:text-slate-300"
            >
                <GripVertical size={18} />
            </div>

            <div className="flex-1 grid grid-cols-12 gap-3">
                {/* Number Badge */}
                <div className="col-span-1 flex items-center justify-center">
                    <span className="bg-slate-700 text-slate-300 text-xs font-bold px-2 py-1 rounded-full">
                        {index + 1}
                    </span>
                </div>

                {/* Action Select */}
                <div className="col-span-3">
                    <Select
                        value={step.action}
                        onValueChange={(val: any) => onUpdate(step.id!, { action: val })}
                    >
                        <SelectTrigger className="w-full bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500">
                            <SelectValue placeholder="动作 (Action)" />
                        </SelectTrigger>
                        <SelectContent className="bg-slate-900 border-slate-700 text-slate-100">
                            {ACTION_OPTIONS.map(opt => (
                                <SelectItem key={opt.value} value={opt.value} className="focus:bg-slate-800 focus:text-slate-100 cursor-pointer">
                                    {opt.label}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Target Description */}
                <div className="col-span-4">
                    <Input
                        placeholder={step.action === 'WAIT' ? '等待条件/秒数 (Wait condition/seconds)' : (step.action === 'GOTO' ? '说明可选 (Note (optional))' : '自然语言描述目标 (Describe target in natural language)')}
                        value={step.target_description || ''}
                        onChange={(e) => onUpdate(step.id!, { target_description: e.target.value })}
                        disabled={['GOTO'].includes(step.action)}
                        className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500 disabled:opacity-50 disabled:bg-slate-900"
                    />
                </div>

                {/* Value Input */}
                <div className="col-span-3">
                    <Input
                        placeholder={step.action === 'GOTO' ? 'https://...' : (step.action === 'TYPE' ? '输入的文本 (Text to type)' : '断言值可选 (Assert value (optional))')}
                        value={step.value || ''}
                        onChange={(e) => onUpdate(step.id!, { value: e.target.value })}
                        disabled={['CLICK', 'WAIT', 'SCROLL'].includes(step.action)}
                        className="bg-slate-950 border-slate-700 text-slate-100 placeholder:text-slate-500 disabled:opacity-50 disabled:bg-slate-900"
                    />
                </div>

                {/* Delete Action */}
                <div className="col-span-1 flex items-center justify-end">
                    <Button variant="ghost" size="icon" className="text-rose-400 hover:bg-rose-500/10 hover:text-rose-300" onClick={() => onRemove(step.id!)}>
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
                <h3 className="text-lg font-semibold flex items-center gap-2 text-slate-100">
                    <span className="bg-indigo-500/10 text-indigo-400 p-1.5 rounded-md">👁️</span>
                    自然语言步骤编排 (Natural Language Step Builder)
                </h3>
                <Button onClick={handleAddStep} size="sm" className="gap-2">
                    <Plus size={16} /> 添加步骤 (Add Step)
                </Button>
            </div>

            {steps.length === 0 ? (
                <div className="text-center py-12 border-2 border-dashed border-slate-800 rounded-lg text-slate-500 bg-slate-900">
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
