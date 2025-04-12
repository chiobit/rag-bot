# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
import os

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

CONFIG = DefaultConfig()

# Create adapter.
SETTINGS = BotFrameworkAdapterSettings(CONFIG.APP_ID, CONFIG.APP_PASSWORD)
ADAPTER = BotFrameworkAdapter(SETTINGS)

# Catch-all for errors.
async def on_error(context: TurnContext, error: Exception):
    print(f"\n❌ [on_turn_error] unhandled error: {error}", file=sys.stderr)
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
        print("✅ 收到 /api/messages")

        if "application/json" in req.headers.get("Content-Type", ""):
            body = await req.json()
            print("📝 解析 JSON 成功")
        else:
            print("❌ Content-Type 錯誤")
            return Response(status=415)

        print("📦 請求內容：", body)

        activity = Activity().deserialize(body)
        print("✅ activity 轉換成功，type:", activity.type)

        auth_header = req.headers.get("Authorization", "")
        print("🔐 Authorization Header:", auth_header[:40] + "...")

        response = await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
        print("✅ 處理完成，response:", response)

        if response:
            return json_response(data=response.body, status=response.status)

        return Response(status=201)

    except Exception as e:
        print("❌ 發生例外錯誤！")
        print(f"[Exception] {e}", file=sys.stderr)
        traceback.print_exc()
        return Response(text=f"500: Internal Server Error\n{e}", status=500)

# 建立 aiohttp 應用程式
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", CONFIG.PORT or 8000))
        print(f"✅ App starting on http://0.0.0.0:{port}")
        web.run_app(APP, host="0.0.0.0", port=port)
    except Exception as error:
        print("❌ 應用啟動時發生錯誤")
        traceback.print_exc()
