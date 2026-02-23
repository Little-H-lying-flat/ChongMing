import { Trash2, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface KeyValuePair {
    key: string;
    value: string;
    description?: string;
}

interface KeyValueEditorProps {
    pairs: KeyValuePair[];
    onChange: (pairs: KeyValuePair[]) => void;
    placeholderKey?: string;
    placeholderValue?: string;
}

export function KeyValueEditor({ pairs, onChange, placeholderKey = "键 (Key)", placeholderValue = "值 (Value)" }: KeyValueEditorProps) {
    const handleAdd = () => {
        onChange([...pairs, { key: "", value: "", description: "" }]);
    };

    const handleRemove = (index: number) => {
        const newPairs = [...pairs];
        newPairs.splice(index, 1);
        onChange(newPairs);
    };

    const handleChange = (index: number, field: keyof KeyValuePair, val: string) => {
        const newPairs = [...pairs];
        newPairs[index][field] = val;
        onChange(newPairs);
    };

    // Auto-add an empty row if the last one is filled, or if empty
    if (pairs.length === 0 || (pairs[pairs.length - 1].key !== "" || pairs[pairs.length - 1].value !== "")) {
        // Technically bad to mutate during render or cause effect infinite loop, it's better to require manual add or just render a dummy empty row.
    }

    return (
        <div className="space-y-2">
            {pairs.map((pair, index) => (
                <div key={index} className="flex items-center gap-2">
                    <Input
                        value={pair.key}
                        onChange={(e) => handleChange(index, "key", e.target.value)}
                        placeholder={placeholderKey}
                        className="flex-1 bg-slate-950 border-slate-700 text-slate-100 h-9 shrink-0 whitespace-nowrap"
                    />
                    <Input
                        value={pair.value}
                        onChange={(e) => handleChange(index, "value", e.target.value)}
                        placeholder={placeholderValue}
                        className="flex-1 bg-slate-950 border-slate-700 text-slate-100 h-9"
                    />
                    <Input
                        value={pair.description || ""}
                        onChange={(e) => handleChange(index, "description", e.target.value)}
                        placeholder="描述 可选 (Description (Optional))"
                        className="flex-1 bg-slate-950 border-slate-700 text-slate-100 h-9"
                    />
                    <Button variant="ghost" size="icon" onClick={() => handleRemove(index)} className="shrink-0 h-9 w-9 text-slate-400 hover:text-rose-400">
                        <Trash2 className="h-4 w-4" />
                    </Button>
                </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={handleAdd} className="mt-2 bg-slate-900 border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-slate-100">
                <Plus className="h-3 w-3 mr-1" /> 添加行 (Add Row)
            </Button>
        </div>
    );
}
