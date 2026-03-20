"""
handlers/router.py — يسجّل جميع الـ handlers في التطبيق
"""

from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters,
)

from core.config import (
    ST_FILE, ST_NAME, ST_TOKEN,
    ST_SC_VALUE, ST_BC_VALUE,
    ST_ENV_KEY, ST_ENV_VAL,
    ST_SCHEDULE_BOT, ST_SCHEDULE_ACTION, ST_SCHEDULE_TIME,
    ST_UPDATE_FILE,
)
from handlers.panel        import PanelHandler
from handlers.bot_mgr      import BotManager
from handlers.bot_ctrl     import BotCtrlHandler
from handlers.env_mgr      import EnvManager
from handlers.scheduler_h  import SchedulerHandler
from handlers.search_h     import SearchHandler
from handlers.notif_h      import NotifHandler
from handlers.media_h      import MediaHandler


def build_handlers(app: Application, pm, scheduler, notifier):
    # ── إنشاء الـ handlers ───────────────────────────────
    panel   = PanelHandler(pm, notifier)
    mgr     = BotManager(pm, notifier)
    bctrl   = BotCtrlHandler(pm)
    envmgr  = EnvManager(pm)
    schedh  = SchedulerHandler(pm, scheduler)
    searchh = SearchHandler(pm)
    notifh  = NotifHandler(notifier)
    mediah  = MediaHandler(pm, bctrl)

    # ── Conversation: إضافة بوت ──────────────────────────
    add_conv = ConversationHandler(
        entry_points=[CommandHandler("add", mgr.cmd_add)],
        states={
            ST_FILE:  [MessageHandler(filters.Document.ALL, mgr.conv_file)],
            ST_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, mgr.conv_name)],
            ST_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, mgr.conv_token),
                CallbackQueryHandler(mgr.conv_skip_token, pattern="^skip_token$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── Conversation: متغيرات البيئة ─────────────────────
    env_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(envmgr.start_add_env, pattern=r"^env_add:\w+$")],
        states={
            ST_ENV_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, envmgr.get_key)],
            ST_ENV_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, envmgr.get_val)],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── Conversation: جدولة ──────────────────────────────
    sched_conv = ConversationHandler(
        entry_points=[
            CommandHandler("schedule", schedh.cmd_schedule),
            CallbackQueryHandler(schedh.start_schedule, pattern=r"^sched_new:[\w]+$"),
        ],
        states={
            ST_SCHEDULE_BOT:    [CallbackQueryHandler(schedh.pick_bot,    pattern=r"^spick:\w+$")],
            ST_SCHEDULE_ACTION: [CallbackQueryHandler(schedh.pick_action, pattern=r"^sact:\w+$")],
            ST_SCHEDULE_TIME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, schedh.get_time)],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── Conversation: تحديث الكود ────────────────────────
    update_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(mgr.start_update, pattern=r"^update:\w+$")],
        states={
            ST_UPDATE_FILE: [MessageHandler(filters.Document.ALL, mgr.recv_update_file)],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── Conversation: self_ctrl ───────────────────────────
    sc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bctrl.sc_start, pattern=r"^sc:[a-z]+$")],
        states={
            ST_SC_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bctrl.sc_text),
                MessageHandler(filters.PHOTO, mediah.sc_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── Conversation: bot_ctrl ────────────────────────────
    bc_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bctrl.bc_start, pattern=r"^bc:[a-z_]+:\w+$")],
        states={
            ST_BC_VALUE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bctrl.bc_text),
                MessageHandler(filters.PHOTO, mediah.bc_photo),
            ],
        },
        fallbacks=[CommandHandler("cancel", mgr.cmd_cancel)],
        allow_reentry=True,
        per_user=True,
        per_message=True,
    )

    # ── تسجيل المحادثات (بالترتيب — الأعلى أولوية أولاً) ─
    for conv in (add_conv, env_conv, sched_conv, update_conv, sc_conv, bc_conv):
        app.add_handler(conv)

    # ── أوامر مباشرة ─────────────────────────────────────
    app.add_handler(CommandHandler("start",     panel.cmd_start))
    app.add_handler(CommandHandler("panel",     panel.cmd_panel))
    app.add_handler(CommandHandler("bots",      panel.cmd_bots))
    app.add_handler(CommandHandler("stats",     panel.cmd_stats))
    app.add_handler(CommandHandler("search",    searchh.cmd_search))
    app.add_handler(CommandHandler("logs",      mgr.cmd_logs))
    app.add_handler(CommandHandler("start_bot", mgr.cmd_start_bot))
    app.add_handler(CommandHandler("stop_bot",  mgr.cmd_stop_bot))
    app.add_handler(CommandHandler("restart",   mgr.cmd_restart_bot))
    app.add_handler(CommandHandler("delete",    mgr.cmd_delete))
    app.add_handler(CommandHandler("cancel",    mgr.cmd_cancel))

    # ── Callbacks (مرتبة من الأكثر تحديداً للأقل) ────────

    # Panel رئيسي
    app.add_handler(CallbackQueryHandler(
        panel.on_cb,
        pattern=r"^(home|list|sys_stats|start_all|stop_all|refresh_panel)$"
    ))

    # إضافة بوت
    app.add_handler(CallbackQueryHandler(mgr.on_cb, pattern=r"^add$"))

    # إجراءات البوت
    app.add_handler(CallbackQueryHandler(
        mgr.on_cb,
        pattern=r"^(info|start|stop|restart|logs|clear_logs|bstats|toggle_ar|del_confirm|del_do|reinstall):"
    ))

    # تحكم هوية البوت
    app.add_handler(CallbackQueryHandler(
        bctrl.on_cb,
        pattern=r"^(bot_ctrl|self_ctrl|bc_fetch|bc_del_photo):"
    ))

    # متغيرات البيئة
    app.add_handler(CallbackQueryHandler(
        envmgr.on_cb,
        pattern=r"^(env_menu|env_del|env_list):"
    ))

    # الجدولة
    app.add_handler(CallbackQueryHandler(
        schedh.on_cb,
        pattern=r"^(sched_menu|sched_del|sched_list|sched_new):"
    ))

    # البحث والتصفية
    app.add_handler(CallbackQueryHandler(
        searchh.on_cb,
        pattern=r"^(search_menu|filter_status:.+|search_result:.+)$"
    ))

    # الإشعارات
    app.add_handler(CallbackQueryHandler(
        notifh.on_cb,
        pattern=r"^(notif_menu|notif_toggle:.+)$"
    ))

    # ── ملفات خارج المحادثة (drag & drop) ───────────────
    app.add_handler(MessageHandler(
        filters.Document.ALL & ~filters.COMMAND,
        mediah.on_doc_free
    ))
