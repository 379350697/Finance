import { useEffect, useRef } from "react";
import type { MinuteBar } from "../api/client";

type Quote = {
  price: number;
  change_pct?: number;
};

function KLineChart({
  bars,
  quote,
  width = 600,
  height = 400,
}: {
  bars: MinuteBar[];
  quote?: Quote;
  width?: number;
  height?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    if (!bars.length) {
      ctx.fillStyle = "#999";
      ctx.font = "14px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("暂无K线数据", width / 2, height / 2);
      return;
    }

    const pad = { top: 20, right: 30, bottom: 60, left: 60 };
    const chartW = width - pad.left - pad.right;
    const volAreaH = 60;
    const priceH = height - pad.top - pad.bottom - volAreaH;

    const highs = bars.map((b) => b.high);
    const lows = bars.map((b) => b.low);
    const maxHigh = Math.max(...highs);
    const minLow = Math.min(...lows);
    const priceRange = maxHigh - minLow || 1;

    const maxVol = Math.max(...bars.map((b) => b.volume || 0), 1);

    const barW = Math.max(2, Math.min(12, chartW / bars.length - 1));
    const gap = (chartW - barW * bars.length) / Math.max(bars.length - 1, 1);
    const x = (i: number) => pad.left + i * (barW + gap);

    const toY = (p: number) => pad.top + ((maxHigh - p) / priceRange) * priceH;

    // Background grid
    ctx.strokeStyle = "#eee";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (priceH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(width - pad.right, y);
      ctx.stroke();
      const price = maxHigh - (priceRange / 4) * i;
      ctx.fillStyle = "#999";
      ctx.font = "10px sans-serif";
      ctx.textAlign = "right";
      ctx.fillText(price.toFixed(2), pad.left - 4, y + 3);
    }

    // Candles
    bars.forEach((bar, i) => {
      const cx = x(i);
      const isUp = bar.close >= bar.open;
      const bodyTop = toY(isUp ? bar.close : bar.open);
      const bodyBot = toY(isUp ? bar.open : bar.close);
      const bodyH = Math.max(1, bodyBot - bodyTop);

      const color = isUp ? "#ef4444" : "#22c55e";
      ctx.strokeStyle = color;
      ctx.fillStyle = isUp ? color : "#fff";

      // Wick
      const wickTop = toY(bar.high);
      const wickBot = toY(bar.low);
      ctx.beginPath();
      ctx.moveTo(cx + barW / 2, wickTop);
      ctx.lineTo(cx + barW / 2, wickBot);
      ctx.stroke();

      // Body
      ctx.fillStyle = isUp ? color : "#fff";
      ctx.fillRect(cx, bodyTop, barW, bodyH);
      ctx.strokeStyle = color;
      ctx.strokeRect(cx, bodyTop, barW, bodyH);
    });

    // Volume bars (bottom)
    const volBaseY = pad.top + priceH + 10;
    bars.forEach((bar, i) => {
      const cx = x(i);
      const vol = bar.volume || 0;
      const volH = (vol / maxVol) * volAreaH;
      const isUp = bar.close >= bar.open;
      ctx.fillStyle = isUp ? "rgba(239,68,68,0.35)" : "rgba(34,197,94,0.35)";
      ctx.fillRect(cx, volBaseY + volAreaH - volH, barW, volH);
    });

    // Volume axis
    ctx.fillStyle = "#999";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(maxVol.toLocaleString(), pad.left - 4, volBaseY + 10);

    // Quote price line (real-time overlay)
    if (quote && quote.price > 0 && quote.price >= minLow && quote.price <= maxHigh) {
      const qy = toY(quote.price);
      ctx.setLineDash([4, 3]);
      ctx.strokeStyle = quote.change_pct && quote.change_pct >= 0 ? "#ef4444" : "#22c55e";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, qy);
      ctx.lineTo(width - pad.right, qy);
      ctx.stroke();
      ctx.setLineDash([]);

      // Price label on the right
      ctx.fillStyle = ctx.strokeStyle;
      ctx.font = "bold 11px monospace";
      ctx.textAlign = "left";
      ctx.fillText(
        quote.price.toFixed(2),
        width - pad.right + 4,
        qy + 4,
      );
    }

    // Time axis
    ctx.fillStyle = "#999";
    ctx.font = "9px sans-serif";
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(bars.length / 6));
    bars.forEach((bar, i) => {
      if (i % step === 0 || i === bars.length - 1) {
        const time = bar.trade_time?.slice(-8, -3) || String(i);
        ctx.fillText(time, x(i) + barW / 2, volBaseY + volAreaH + 14);
      }
    });
  }, [bars, quote, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width: `${width}px`, height: `${height}px`, borderRadius: "8px" }}
    />
  );
}

export default KLineChart;
