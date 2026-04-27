"""OAuth callback HTML page.

When the OAuth GET callback is used in popup mode, we return a small HTML page
that posts the authorization code back to the opener window via postMessage,
then closes itself.
"""

OAUTH_CALLBACK_HTML = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>OpenAI 授权中…</title></head>
<body>
<p>正在完成授权，请稍候…</p>
<script>
(function() {
  var params = new URLSearchParams(window.location.search);
  var code = params.get("code");
  var state = params.get("state");
  if (window.opener && code) {
    window.opener.postMessage({type: "oauth_callback", code: code, state: state}, "*");
    window.close();
  } else {
    document.body.innerHTML = "<p>授权完成。您可以关闭此窗口。</p>";
  }
})();
</script>
</body>
</html>"""
