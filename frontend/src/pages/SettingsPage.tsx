import { Terminal, LogOut, CheckCircle, Settings } from "lucide-react";
import { useState, useEffect } from "react";
import { getOAuthStatus, logoutOAuth, startDeviceAuth, pollDeviceAuth, DeviceAuthStartResult } from "../api/client";

export function SettingsPage() {
  const [oauthAuthed, setOauthAuthed] = useState(false);
  const [deviceAuth, setDeviceAuth] = useState<DeviceAuthStartResult | null>(null);
  const [isStartingDeviceAuth, setIsStartingDeviceAuth] = useState(false);
  const [pollError, setPollError] = useState("");
  const [isChecking, setIsChecking] = useState(false);

  const refreshOAuthStatus = () => {
    getOAuthStatus()
      .then((s) => {
        setOauthAuthed(s.authenticated);
        if (s.authenticated) setDeviceAuth(null);
      })
      .catch(() => setOauthAuthed(false));
  };

  useEffect(() => {
    refreshOAuthStatus();
  }, []);

  const handleStartDeviceAuth = async () => {
    setIsStartingDeviceAuth(true);
    setPollError("");
    try {
      const res = await startDeviceAuth();
      setDeviceAuth(res);
    } catch (err) {
      console.error("Failed to start device auth:", err);
      setPollError("无法获取设备码，请重试。");
    } finally {
      setIsStartingDeviceAuth(false);
    }
  };

  const handleCheckAuthStatus = async () => {
    if (!deviceAuth) return;
    setIsChecking(true);
    setPollError("");
    try {
      const res = await pollDeviceAuth(deviceAuth.device_auth_id, deviceAuth.user_code);
      if (res.status === "authenticated") {
        setOauthAuthed(true);
        setDeviceAuth(null);
      } else {
        setPollError("授权尚未完成，请在浏览器中确认后再重试。");
      }
    } catch (err) {
      setPollError("查询状态失败或代码已过期。");
    } finally {
      setIsChecking(false);
    }
  };

  const handleLogout = async () => {
    await logoutOAuth().catch(() => {});
    setOauthAuthed(false);
  };

  return (
    <div className="page-container settings-page">
      <header className="page-header">
        <h2>系统设置</h2>
        <p>管理账号授权与系统参数</p>
      </header>

      <div className="settings-section">
        <h3>OpenAI Codex 账号授权</h3>
        <p className="settings-desc">通过设备码方式安全地连接你的 ChatGPT 账号，无需暴露密码。</p>
        
        <div className="oauth-card">
          {oauthAuthed ? (
            <div className="oauth-status oauth-status--authed">
              <CheckCircle size={24} color="#10a37f" />
              <div className="oauth-status-text">
                <strong>已连接</strong>
                <span>你的账号已成功授权，可以正常使用相关服务。</span>
              </div>
              <button type="button" className="btn btn--danger" onClick={handleLogout}>
                <LogOut size={16} /> 退出登录
              </button>
            </div>
          ) : deviceAuth ? (
            <div className="device-auth-flow">
              <p className="step-title">请按照以下步骤完成授权：</p>
              <div className="auth-step">
                <span className="step-num">1</span>
                <div className="step-content">
                  <span>在浏览器中打开验证链接：</span>
                  <a href={deviceAuth.verification_url} target="_blank" rel="noopener noreferrer">
                    {deviceAuth.verification_url}
                  </a>
                </div>
              </div>
              <div className="auth-step">
                <span className="step-num">2</span>
                <div className="step-content">
                  <span>输入以下一次性代码：</span>
                  <code className="user-code-display">{deviceAuth.user_code}</code>
                </div>
              </div>
              <div className="auth-step">
                <span className="step-num">3</span>
                <div className="step-content">
                  <span>完成授权后点击下方按钮：</span>
                  <button 
                    type="button" 
                    className="btn btn--primary btn--auth-complete" 
                    onClick={handleCheckAuthStatus}
                    disabled={isChecking}
                  >
                    {isChecking ? "查询中..." : "我已经授权完成"}
                  </button>
                </div>
              </div>
              {pollError && <p className="error-text">{pollError}</p>}
            </div>
          ) : (
            <div className="oauth-status oauth-status--unauthed">
              <div className="oauth-status-text">
                <strong>未连接</strong>
                <span>请点击下方按钮开始授权流程。</span>
              </div>
              <button 
                type="button" 
                className="btn btn--primary" 
                onClick={handleStartDeviceAuth}
                disabled={isStartingDeviceAuth}
              >
                <Terminal size={16} /> {isStartingDeviceAuth ? "生成中..." : "获取设备码并登录"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
