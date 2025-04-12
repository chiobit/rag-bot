import os
import sys
import traceback
import logging
from datetime import datetime

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import (
    BotFrameworkAdapterSettings,
    TurnContext,
    BotFrameworkAdapter,
)
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity, ActivityTypes

from bot import MyBot
from config import DefaultConfig

# ✅ 初始化 logger
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = DefaultConfig()

# ✅ 自動切換驗證模式
if os.environ.get("BOT_AUTH_DISABLED", "false").lower() == "true":
    logger.warning("⚠️ BOT_AUTH_DISABLED 模式開啟，將略過驗證")
    SETTINGS = BotFrameworkAdapterSettings("", "")
else:
    logger.info("🔐 使用正式模式，啟用 App ID / Secret 驗證")
    SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)

ADAPTER = BotFrameworkAdapter(SETTINGS)

# ❗錯誤處理
async def on_error(context: TurnContext, error: Exception):
    logger.error("❌ [on_turn_error] 發生未處理錯誤：%s", error)
    traceback.print_exc()

    await context.send_activity("⚠️ The bot encountered an error.")
    await context.send_activity("Please fix the bot source code.")

    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=str(error),
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)

ADAPTER.on_turn_error = on_error

# ✅ 建立 bot 實例
BOT = MyBot()

# ✅ POST /api/messages handler
async def messages(req: Request) -> Response:
    try:
        logger.info("📥 收到請求：%s %s", req.method, req.path)

        content_type = req.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.warning("❌ Content-Type 錯誤：%s", content_type)
            return Response(status=415, text="Unsupported Media Type")

        body = await req.json()
        logger.info("📦 請求內容：%s", body)

        activity = Activity().deserialize(body)
        logger.info("✅ 解析成功，Activity type: %s", activity.type)

        auth_header = req.headers.get("Authorization", "")
        if not auth_header:
            logger.warning("⚠️ 沒有 Authorization header")
        else:
            logger.info("🔐 Authorization: %s...", auth_header[:40])

        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        logger.info("✅ 處理完成")

        if response:
            logger.info("📝 有回應，狀態：%s", response.status)
            return json_response(data=response.body, status=response.status)

        return Response(status=201)

    except Exception as e:
        logger.exception("❌ 發生例外：%s", e)
        traceback.print_exc()
        return Response(text=f"500: Internal Server Error\n{e}", status=500)

# ✅ aiohttp app 初始化
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", CONFIG.PORT or 8000))
        logger.info("🚀 Bot App 啟動中 http://0.0.0.0:%s", port)
        web.run_app(APP, host="0.0.0.0", port=port)
    except Exception as error:
        logger.exception("❌ App 啟動錯誤：%s", error)
        traceback.print_exc()
