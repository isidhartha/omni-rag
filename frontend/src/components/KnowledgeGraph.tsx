import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import axios from "axios";
import { Network, RefreshCw } from "lucide-react";

interface GraphNode {
  id: string;
  label: string;
  type: string;
  level: number;
}

interface GraphLink {
  source: string;
  target: string;
  weight: number;
}

interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

const DOC_TYPE_COLORS: Record<string, string> = {
  pdf: "#3b82f6",
  image: "#8b5cf6",
  code: "#10b981",
  audio: "#f59e0b",
  video: "#ef4444",
  url: "#06b6d4",
  unknown: "#6b7280",
};

interface Props {
  docId?: string;
}

export default function KnowledgeGraph({ docId }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [loading, setLoading] = useState(false);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadGraph(id: string) {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get<GraphData>(`/api/v1/graph/${id}`);
      setGraph(res.data);
    } catch (e: unknown) {
      setError("Failed to load graph.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (docId) loadGraph(docId);
  }, [docId]);

  useEffect(() => {
    if (!graph || !svgRef.current) return;
    renderGraph(graph, svgRef.current);
  }, [graph]);

  function renderGraph(data: GraphData, svgEl: SVGSVGElement) {
    d3.select(svgEl).selectAll("*").remove();

    const W = svgEl.clientWidth || 600;
    const H = svgEl.clientHeight || 400;

    const svg = d3
      .select(svgEl)
      .attr("viewBox", `0 0 ${W} ${H}`)
      .style("background", "transparent");

    const g = svg.append("g");

    svg.call(
      d3.zoom<SVGSVGElement, unknown>().on("zoom", (event) => {
        g.attr("transform", event.transform);
      }) as any
    );

    const simulation = d3
      .forceSimulation<GraphNode & d3.SimulationNodeDatum>(data.nodes as any)
      .force(
        "link",
        d3
          .forceLink<GraphNode & d3.SimulationNodeDatum, GraphLink>(data.links as any)
          .id((d: any) => d.id)
          .distance(100)
      )
      .force("charge", d3.forceManyBody().strength(-200))
      .force("center", d3.forceCenter(W / 2, H / 2))
      .force("collision", d3.forceCollide(40));

    const link = g
      .append("g")
      .selectAll("line")
      .data(data.links)
      .join("line")
      .attr("stroke", "#374151")
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0.6);

    const node = g
      .append("g")
      .selectAll("g")
      .data(data.nodes)
      .join("g")
      .attr("cursor", "pointer")
      .call(
        d3
          .drag<SVGGElement, GraphNode & d3.SimulationNodeDatum>()
          .on("start", (event, d: any) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d: any) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d: any) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as any
      );

    node
      .append("circle")
      .attr("r", (d) => (d.level === 0 ? 20 : 14))
      .attr("fill", (d) => DOC_TYPE_COLORS[d.type] || DOC_TYPE_COLORS.unknown)
      .attr("fill-opacity", (d) => (d.level === 0 ? 0.9 : 0.6))
      .attr("stroke", "#1f2937")
      .attr("stroke-width", 2);

    node
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .attr("y", (d) => (d.level === 0 ? 30 : 24))
      .attr("fill", "#d1d5db")
      .attr("font-size", "10px")
      .attr("font-family", "Inter, sans-serif")
      .text((d) => (d.label.length > 16 ? d.label.slice(0, 14) + "…" : d.label));

    simulation.on("tick", () => {
      link
        .attr("x1", (d: any) => d.source.x)
        .attr("y1", (d: any) => d.source.y)
        .attr("x2", (d: any) => d.target.x)
        .attr("y2", (d: any) => d.target.y);

      node.attr("transform", (d: any) => `translate(${d.x},${d.y})`);
    });
  }

  if (!docId) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-600 gap-2">
        <Network size={32} />
        <p className="text-sm">Select a document to explore its knowledge graph</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900/60 z-10 rounded-xl">
          <RefreshCw size={24} className="text-brand-400 animate-spin" />
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
      <svg ref={svgRef} className="w-full h-full" />
      {graph && (
        <div className="absolute top-2 right-2 flex flex-wrap gap-2">
          {Object.entries(DOC_TYPE_COLORS).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1 text-xs text-gray-400">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              {type}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
