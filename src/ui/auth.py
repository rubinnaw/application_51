import flet as ft
import random
from utils.cache import ChatCache
from api.openrouter import OpenRouterClient

class AuthUI:
    def __init__(self, page: ft.Page, on_auth_success):
        self.page = page
        self.cache = ChatCache()
        self.on_auth_success = on_auth_success

        self.input_style = {
            "width": 300,
            "height": 50,
            "border_color": ft.colors.BLUE_400,
            "focused_border_color": ft.colors.BLUE_600,
            "cursor_color": ft.colors.BLUE_600,
        }

    def generate_pin(self):
        return ''.join([str(random.randint(0, 9)) for _ in range(4)])

    async def check_api_key(self, api_key: str):
        try:
            client = OpenRouterClient(api_key=api_key)
            balance = client.get_balance()
            if balance == "Ошибка":
                return False, "Неверный API ключ"
            
            balance_value = float(balance.lstrip('$'))
            if balance_value <= 0:
                return False, "Недостаточно средств на балансе"
                
            return True, None
        except Exception as e:
            return False, str(e)

    def show_error(self, message: str):
        self.page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(message, color=ft.colors.RED_500),
                bgcolor=ft.colors.GREY_900
            )
        )
        self.page.update()

    async def handle_first_login(self, e):
        api_key = self.api_key_input.value
        telegram_id = self.telegram_id_input.value

        if not api_key or not telegram_id:
            self.show_error("Заполните все поля")
            return

        is_valid, error = await self.check_api_key(api_key)
        if not is_valid:
            self.show_error(error)
            return

        pin = self.generate_pin()
        self.cache.save_auth_data(api_key, pin, telegram_id)
        
        async def handle_ok_click(e):
            await self.close_dialog_and_proceed(dialog)
            
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Ваш PIN-код"),
            content=ft.Column([
                ft.Text("Сохраните этот PIN-код. Он потребуется для входа в приложение:"),
                ft.Text(pin, size=30, weight=ft.FontWeight.BOLD),
            ]),
            actions=[
                ft.TextButton("OK", on_click=handle_ok_click),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    async def close_dialog_and_proceed(self, dialog):
        import asyncio
        dialog.open = False
        await self.page.update_async()
        # Добавляем небольшую задержку перед открытием основного окна
        await asyncio.sleep(0.5)  # 500ms = 0.5s
        await self.on_auth_success()

    async def handle_pin_login(self, e):
        pin = self.pin_input.value
        if not pin:
            self.show_error("Введите PIN")
            return

        if self.cache.verify_pin(pin):
            await self.on_auth_success()
        else:
            self.show_error("Неверный PIN")

    async def handle_reset(self, e):
        self.cache.clear_auth_data()
        await self.show_first_login()

    async def show_first_login(self):
        self.api_key_input = ft.TextField(
            label="API ключ OpenRouter",
            **self.input_style
        )
        self.telegram_id_input = ft.TextField(
            label="Telegram Chat ID",
            **self.input_style
        )

        self.page.clean()
        self.page.add(
            ft.Column(
                controls=[
                    ft.Text("Первый вход", size=30, weight=ft.FontWeight.BOLD),
                    self.api_key_input,
                    self.telegram_id_input,
                    ft.ElevatedButton(
                        text="Войти",
                        on_click=self.handle_first_login,
                        style=ft.ButtonStyle(
                            color=ft.colors.WHITE,
                            bgcolor=ft.colors.BLUE_400,
                        )
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        self.page.update()

    async def show_pin_login(self):
        self.pin_input = ft.TextField(
            label="Введите PIN",
            password=True,
            **self.input_style
        )

        self.page.clean()
        self.page.add(
            ft.Column(
                controls=[
                    ft.Text("Вход", size=30, weight=ft.FontWeight.BOLD),
                    self.pin_input,
                    ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                text="Войти",
                                on_click=self.handle_pin_login,
                                style=ft.ButtonStyle(
                                    color=ft.colors.WHITE,
                                    bgcolor=ft.colors.BLUE_400,
                                )
                            ),
                            ft.TextButton(
                                text="Сбросить ключ",
                                on_click=self.handle_reset,
                            )
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=20
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=20
            )
        )
        self.page.update()

    async def show_auth(self):
        auth_data = self.cache.get_auth_data()
        if auth_data is None:
            await self.show_first_login()
        else:
            await self.show_pin_login()
