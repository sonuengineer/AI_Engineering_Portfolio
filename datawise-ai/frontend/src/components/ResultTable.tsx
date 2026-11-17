import type { Cell } from "../types";
import { formatCell } from "./format";

export function ResultTable({ columns, rows, highlight = [] }: { columns: string[]; rows: Cell[][]; highlight?: number[] }) {
  const hl = new Set(highlight);
  return (
    <div className="max-h-96 overflow-auto rounded-md border border-slate-200">
      <table className="min-w-full text-sm">
        <caption className="sr-only">Query results</caption>
        <thead className="sticky top-0 bg-slate-100">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium text-slate-500">#</th>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 text-left font-medium text-slate-700">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={hl.has(i) ? "bg-teal-50" : i % 2 ? "bg-white" : "bg-slate-50/50"}>
              <td className="px-3 py-1.5 text-slate-400">{i + 1}</td>
              {r.map((v, j) => (
                <td key={j} className={`px-3 py-1.5 ${typeof v === "number" ? "text-right tabular-nums" : ""}`}>
                  {formatCell(columns[j] ?? "", v)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
