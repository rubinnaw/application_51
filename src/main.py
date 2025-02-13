import flet as ft
from api.openrouter import OpenRouterClient
from ui.styles import AppStyles
from ui.components import MessageBubble, ModelSelector
from ui.auth import AuthUI
from utils.cache import ChatCache
from utils.logger import AppLogger
from utils.analytics import Analytics
from utils.monitor import PerformanceMonitor
from utils.notifications import send_telegram_notification
import asyncio
import time
import json
from datetime import datetime
import os

# Список предпочтительных моделей
PREFERRED_MODELS = [
    "deepseek/deepseek-coder",
    "anthropic/claude-3-sonnet",
    "deepseek/deepseek-r1-distill-llama-70b:free"
]

class ChatApp:
    def __init__(self):
        self.cache = ChatCache()
        self.logger = AppLogger()
        self.analytics = Analytics(self.cache)
        self.monitor = PerformanceMonitor()
        self.exports_dir = "exports"
        os.makedirs(self.exports_dir, exist_ok=True)

    async def initialize(self, page: ft.Page):
        """Инициализация приложения"""
        async def on_auth_success():
            try:
                await self.show_main_ui(page)
            except Exception as e:
                self.logger.error(f"Ошибка при переходе на главный экран: {e}")
                snack = ft.SnackBar(
                    content=ft.Text(f"Ошибка: {str(e)}", color=ft.Colors.RED_500),
                    bgcolor=ft.Colors.GREY_900
                )
                page.snack_bar = snack
                snack.open = True
                page.update()

        auth_ui = AuthUI(page, on_auth_success)
        await auth_ui.show_auth()

    def initialize_api_client(self):
        auth_data = self.cache.get_auth_data()
        if not auth_data:
            self.logger.error("Не удалось получить данные аутентификации")
            raise ValueError("Не удалось получить данные аутентификации")
            
        api_key, _, _ = auth_data
        try:
            self.api_client = OpenRouterClient(api_key=api_key)
            balance = self.api_client.get_balance(validate=True)
            if balance == "Ошибка":
                self.logger.error("Неверный API ключ при инициализации")
                raise ValueError("Неверный API ключ")
            
            # Отправляем уведомление о балансе
            send_telegram_notification(f"Текущий баланс: {balance}")
                
            self.balance_text = ft.Text(
                f"Баланс: {balance}",
                **AppStyles.BALANCE_TEXT
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации API клиента: {e}")
            raise ValueError(f"Ошибка инициализации API клиента: {str(e)}")

    def filter_and_sort_models(self, models):
        """Фильтрация и сортировка моделей"""
        preferred = []
        others = []
        
        for model in models:
            if model['id'] in PREFERRED_MODELS:
                preferred.append(model)
            else:
                others.append(model)
                
        # Сортируем предпочтительные модели в том же порядке, что и в PREFERRED_MODELS
        preferred.sort(key=lambda x: PREFERRED_MODELS.index(x['id']))
        
        return preferred + others

    def load_chat_history(self):
        try:
            history = self.cache.get_chat_history()
            for msg in reversed(history):
                _, model, user_message, ai_response, timestamp, tokens = msg
                self.chat_history.controls.extend([
                    MessageBubble(
                        message=user_message,
                        is_user=True
                    ),
                    MessageBubble(
                        message=ai_response,
                        is_user=False
                    )
                ])
        except Exception as e:
            self.logger.error(f"Ошибка загрузки истории чата: {e}")

    async def show_main_ui(self, page: ft.Page):
        page.clean()
        
        self.initialize_api_client()
        
        for key, value in AppStyles.PAGE_SETTINGS.items():
            setattr(page, key, value)

        AppStyles.set_window_size(page)

        # Get and filter models
        all_models = self.api_client.get_models()
        models = self.filter_and_sort_models(all_models)
        self.model_dropdown = ModelSelector(models)
        self.model_dropdown.value = models[0]['id'] if models else None

        async def send_message_click(e):
            if not self.message_input.value:
                return

            try:
                self.message_input.border_color = ft.Colors.BLUE_400
                page.update()

                start_time = time.time()
                user_message = self.message_input.value
                self.message_input.value = ""
                page.update()

                self.chat_history.controls.append(
                    MessageBubble(message=user_message, is_user=True)
                )

                loading = ft.ProgressRing()
                self.chat_history.controls.append(loading)
                page.update()

                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self.api_client.send_message(
                        user_message, 
                        self.model_dropdown.value
                    )
                )

                self.chat_history.controls.remove(loading)

                if "error" in response:
                    error_text = str(response["error"])
                    if "unsupported_country_region_territory" in error_text:
                        error_text = "Модель недоступна в вашем регионе. Пожалуйста, выберите другую модель."
                    elif "temporarily unavailable" in error_text:
                        error_text = "Модель временно недоступна. Пожалуйста, выберите другую модель."
                    
                    response_text = f"Ошибка: {error_text}"
                    tokens_used = 0
                    self.logger.error(f"Ошибка API: {response['error']}")
                else:
                    response_text = response["choices"][0]["message"]["content"]
                    tokens_used = response.get("usage", {}).get("total_tokens", 0)

                self.cache.save_message(
                    model=self.model_dropdown.value,
                    user_message=user_message,
                    ai_response=response_text,
                    tokens_used=tokens_used
                )

                self.chat_history.controls.append(
                    MessageBubble(message=response_text, is_user=False)
                )

                response_time = time.time() - start_time
                self.analytics.track_message(
                    model=self.model_dropdown.value,
                    message_length=len(user_message),
                    response_time=response_time,
                    tokens_used=tokens_used
                )

                self.monitor.log_metrics(self.logger)
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка отправки сообщения: {e}")
                self.message_input.border_color = ft.Colors.RED_500

                snack = ft.SnackBar(
                    content=ft.Text(
                        str(e),
                        color=ft.Colors.RED_500,
                        weight=ft.FontWeight.BOLD
                    ),
                    bgcolor=ft.Colors.GREY_900,
                    duration=5000,
                )
                page.snack_bar = snack
                snack.open = True
                page.update()

        def show_error_snack(page, message: str):
            snack = ft.SnackBar(
                content=ft.Text(
                    message,
                    color=ft.Colors.RED_500
                ),
                bgcolor=ft.Colors.GREY_900,
                duration=5000,
            )
            page.snack_bar = snack
            snack.open = True
            page.update()

        async def show_analytics(e):
            stats = self.analytics.get_statistics()

            dialog = ft.AlertDialog(
                title=ft.Text("Аналитика"),
                content=ft.Column([
                    ft.Text(f"Всего сообщений: {stats['total_messages']}"),
                    ft.Text(f"Всего токенов: {stats['total_tokens']}"),
                    ft.Text(f"Среднее токенов/сообщение: {stats['tokens_per_message']:.2f}"),
                    ft.Text(f"Сообщений в минуту: {stats['messages_per_minute']:.2f}")
                ]),
                actions=[
                    ft.TextButton("Закрыть", on_click=lambda e: close_dialog(dialog)),
                ],
            )

            page.dialog = dialog
            dialog.open = True
            page.update()

        async def clear_history(e):
            try:
                self.cache.clear_history()
                self.analytics.clear_data()
                self.chat_history.controls.clear()
                page.update()
                
            except Exception as e:
                self.logger.error(f"Ошибка очистки истории: {e}")
                show_error_snack(page, f"Ошибка очистки истории: {str(e)}")

        async def confirm_clear_history(e):
            def close_dlg(e):
                close_dialog(dialog)

            async def clear_confirmed(e):
                await clear_history(e)
                close_dialog(dialog)

            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Подтверждение удаления"),
                content=ft.Text("Вы уверены? Это действие нельзя отменить!"),
                actions=[
                    ft.TextButton("Отмена", on_click=close_dlg),
                    ft.TextButton("Очистить", on_click=clear_confirmed),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            page.dialog = dialog
            dialog.open = True
            page.update()
            
        def close_dialog(dialog):
            dialog.open = False
            page.update()

        async def save_dialog(e):
            try:
                history = self.cache.get_chat_history()

                dialog_data = []
                for msg in history:
                    dialog_data.append({
                        "timestamp": msg[4],
                        "model": msg[1],
                        "user_message": msg[2],
                        "ai_response": msg[3],
                        "tokens_used": msg[5]
                    })

                filename = f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                filepath = os.path.join(self.exports_dir, filename)

                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(dialog_data, f, ensure_ascii=False, indent=2, default=str)

                dialog = ft.AlertDialog(
                    modal=True,
                    title=ft.Text("Диалог сохранен"),
                    content=ft.Column([
                        ft.Text("Путь сохранения:"),
                        ft.Text(filepath, selectable=True, weight=ft.FontWeight.BOLD),
                    ]),
                    actions=[
                        ft.TextButton("OK", on_click=lambda e: close_dialog(dialog)),
                        ft.TextButton("Открыть папку", 
                            on_click=lambda e: os.startfile(self.exports_dir)
                        ),
                    ],
                )

                page.dialog = dialog
                dialog.open = True
                page.update()

            except Exception as e:
                self.logger.error(f"Ошибка сохранения: {e}")
                show_error_snack(page, f"Ошибка сохранения: {str(e)}")

        self.message_input = ft.TextField(**AppStyles.MESSAGE_INPUT)
        self.chat_history = ft.ListView(**AppStyles.CHAT_HISTORY)

        self.load_chat_history()

        save_button = ft.ElevatedButton(
            on_click=save_dialog,
            **AppStyles.SAVE_BUTTON
        )

        clear_button = ft.ElevatedButton(
            on_click=confirm_clear_history,
            **AppStyles.CLEAR_BUTTON
        )

        send_button = ft.ElevatedButton(
            on_click=send_message_click,
            **AppStyles.SEND_BUTTON
        )

        analytics_button = ft.ElevatedButton(
            on_click=show_analytics,
            **AppStyles.ANALYTICS_BUTTON
        )

        control_buttons = ft.Row(  
            controls=[
                save_button,
                analytics_button,
                clear_button
            ],
            **AppStyles.CONTROL_BUTTONS_ROW
        )

        input_row = ft.Row(
            controls=[
                self.message_input,
                send_button
            ],
            **AppStyles.INPUT_ROW
        )

        controls_column = ft.Column(
            controls=[
                input_row,
                control_buttons
            ],
            **AppStyles.CONTROLS_COLUMN
        )

        balance_container = ft.Container(
            content=self.balance_text,
            **AppStyles.BALANCE_CONTAINER
        )

        model_selection = ft.Column(
            controls=[
                self.model_dropdown.search_field,
                self.model_dropdown,
                balance_container
            ],
            **AppStyles.MODEL_SELECTION_COLUMN
        )

        self.main_column = ft.Column(
            controls=[
                model_selection,
                self.chat_history,
                controls_column
            ],
            **AppStyles.MAIN_COLUMN
        )

        page.add(self.main_column)
        page.update()
        
        self.monitor.get_metrics()
        self.logger.info("Приложение запущено")

def main(page: ft.Page):
    app = ChatApp()
    page.title = "AI Chat"
    
    # Set window size
    page.window_width = 800
    page.window_height = 600
    page.update()
    
    asyncio.run(app.initialize(page))

if __name__ == "__main__":
    ft.app(target=main)
