"""인증번호 메일 HTML 템플릿 — 단정 미니멀, 인라인 CSS, 테이블 레이아웃."""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:system-ui,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:#1f2937;">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:#f3f4f6;">
  <tr><td align="center" style="padding:40px 16px;">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:480px;background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;">
      <tr><td align="center" style="padding:40px 32px 8px;">
        <h1 style="margin:0;font-size:22px;font-weight:700;color:#111827;line-height:1.3;">{title}</h1>
      </td></tr>
      <tr><td style="padding:16px 32px 0;">
        <p style="margin:0;font-size:15px;line-height:1.6;color:#374151;">{greeting}</p>
        <p style="margin:8px 0 0;font-size:15px;line-height:1.6;color:#374151;">{intro}</p>
      </td></tr>
      <tr><td align="center" style="padding:24px 32px;">
        <div style="display:inline-block;padding:18px 28px;background:#f5f3ff;border:1px solid #e0d8fb;border-radius:8px;">
          <span style="font-family:'SF Mono',Menlo,Consolas,monospace;font-size:32px;font-weight:700;letter-spacing:6px;color:#7c3aed;">{code}</span>
        </div>
      </td></tr>
      <tr><td style="padding:0 32px 24px;">
        <p style="margin:0;font-size:14px;line-height:1.6;color:#6b7280;">{description}</p>
        <p style="margin:8px 0 0;font-size:14px;line-height:1.6;color:#6b7280;">인증번호는 <strong style="color:#1f2937;">10분간</strong> 유효합니다.</p>
      </td></tr>
      <tr><td style="padding:24px 32px 32px;border-top:1px solid #f3f4f6;">
        <p style="margin:0;font-size:13px;line-height:1.5;color:#9ca3af;">본인이 요청하지 않았다면 이 메일을 무시해 주세요.</p>
        <p style="margin:8px 0 0;font-size:13px;line-height:1.5;color:#9ca3af;">— 피트니스스타 HiFIS</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""
