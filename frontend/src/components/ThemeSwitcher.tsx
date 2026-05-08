import { Moon, Sun } from "lucide-react";
import { useTheme, type ThemeId } from "../ThemeContext";

const labels: Record<ThemeId, string> = {
  "terminal-dark": "暗色终端",
  "chinese-ink": "中式墨韵",
};

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="theme-switcher">
      {(["terminal-dark", "chinese-ink"] as ThemeId[]).map((t) => (
        <button
          key={t}
          aria-pressed={theme === t}
          className="theme-switcher-btn"
          onClick={() => setTheme(t)}
          type="button"
          title={labels[t]}
        >
          {t === "terminal-dark" ? <Moon size={15} /> : <Sun size={15} />}
          <span>{labels[t]}</span>
        </button>
      ))}
    </div>
  );
}
