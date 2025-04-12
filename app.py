# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

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

# ✅ 設定 logging，會輸出到 stdout → Azure Log Stream 可看見
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG = DefaultConfig()

# ✅ 可選：開發模式允許跳過認證（用於 Postman 測試）
if os.environ.get("BOT_AUTH_DISABLED", "false").lower() == "true":
    logger.warning("⚠️ BOT_AUTH_DISABLED 已啟用，將跳過驗證")
    SETTINGS = BotFrameworkAdapterSettings("", "")
else:
    SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)

ADAPTER = BotFrameworkAdapter(SETTINGS)


# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    logger.error("❌ [on_turn_error] 發生未處理錯誤：%s", error)
    traceback.print_exc()

    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity("To continue to run this bot, please fix the bot source code.")

    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=f"{error}",
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)

ADAPTER.on_turn_error = on_error

# Create the Bot
BOT = MyBot()

# Listen for incoming requests on /api/messages
async def messages(req: Request) -> Response:
    try:
        logger.info("📥 收到請求：%s %s", req.method, req.path)

        content_type = req.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            logger.warning("❌ 錯誤的 Content-Type：%s", content_type)
            return Response(status=415, text="Unsupported Media Type")

        body = await req.json()
        logger.info("📦 JSON 請求內容：%s", body)

        activity = Activity().deserialize(body)
        logger.info("✅ 成功解析 Activity，type: %s", activity.type)

        auth_header = req.headers.get("Authorization", "")
        if not auth_header:
            logger.warning("⚠️ 未提供 Authorization header")
        else:
            logger.info("🔐 Authorization 開頭: %s...", auth_header[:40])

        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        logger.info("✅ Bot 處理完成")

        if response:
            logger.info("📝 有回傳 Response，狀態碼：%s", response.status)
            return json_response(data=response.body, status=response.status)

        return Response(status=201)

    except Exception as e:
        logger.exception("❌ 發生例外錯誤：%s", e)
        traceback.print_exc()
        return Response(text=f"500: Internal Server Error\n{e}", status=500)

# 建立 aiohttp 應用程式
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", CONFIG.PORT or 8000))
        logger.info("🚀 App 啟動於 http://0.0.0.0:%s", port)
        web.run_app(APP, host="0.0.0.0", port=port)
    except Exception as error:
        logger.exception("❌ 應用啟動失敗：%s", error)
        traceback.print_exc()
