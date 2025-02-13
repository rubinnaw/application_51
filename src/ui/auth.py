import flet as ft
import random
from utils.cache import ChatCache
from api.openrouter import OpenRouterClient

class AuthUI:
    """
    Класс для управления интерфейсом аутентификации.
    """
    def __init__(self, page: ft.Page, on_auth_success):
        self.page = page
        self.cache = ChatCache()
        self.on_auth_success = on_auth_success

        # Стили для компонентов
        self.input_style = {
            "width": 300,
            "height": 50,
            "border_color": ft.colors.BLUE_400,
            "focused_border_color": ft.colors.BLUE_600,
            "cursor_color": ft.colors.BLUE_600,
        }

    def generate_pin(self):
        """Генерация 4-значного PIN-кода"""
        return ''.join([str(random.randint(0, 9)) for _ in range(4)])

    async def check_api_key(self, api_key: str):
        """Проверка API ключа и его баланса"""
        try:
            client = OpenRouterClient()
            client.api_key = api_key
            balance = client.get_balance()
            if balance == "Ошибка":
                return False, "Неверный API ключ"
            
            # Извлекаем числовое значение баланса
            balance_value = float(balance.lstrip('$'))
            if balance_value <= 0:
                return False, "Недостаточно средств на балансе"
                
            return True, None
        except Exception as e:
            return False, str(e)

    def show_error(self, message: str):
        """Отображение ошибки"""
        self.page.show_snack_bar(
            ft.SnackBar(
                content=ft.Text(message, color=ft.colors.RED_500),
                bgcolor=ft.colors.GREY_900
            )
        )

    async def handle_first_login(self, e):
        """Обработка первого входа"""
        api_key = self.api_key_input.value
        telegram_id = self.telegram_id_input.value

        if not api_key or not telegram_id:
            self.show_error("Заполните все поля")
            return

        # Проверка API ключа
        is_valid, error = await self.check_api_key(api_key)
        if not is_valid:
            self.show_error(error)
            return

        # Генерация PIN
        pin = self.generate_pin()
        
        # Сохранение данных
        self.cache.save_auth_data(api_key, pin, telegram_id)
        
        # Показ PIN пользователю
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Ваш PIN-код"),
            content=ft.Column([
                ft.Text("Сохраните этот PIN-код. Он потребуется для входа в приложение:"),
                ft.Text(pin, size=30, weight=ft.FontWeight.BOLD),
            ]),
            actions=[
                ft.TextButton("OK", on_click=lambda _: self.close_dialog_and_proceed(dialog)),
            ],
        )

        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def close_dialog_and_proceed(self, dialog):
        """Закрытие диалога и переход к основному приложению"""
        dialog.open = False
        self.page.update()
        self.on_auth_success()

    async def handle_pin_login(self, e):
        """Обработка входа по PIN"""
        pin = self.pin_input.value
        if not pin:
            self.show_error("Введите PIN")
            return

        if self.cache.verify_pin(pin):
            self.on_auth_success()
        else:
            self.show_error("Неверный PIN")

    async def handle_reset(self, e):
        """Обработка сброса ключа"""
        self.cache.clear_auth_data()
        self.show_first_login()

    def show_first_login(self):
        """Отображение формы первого входа"""
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

    def show_pin_login(self):
        """Отображение формы входа по PIN"""
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

    def show_auth(self):
        """Отображение нужной формы входа"""
        auth_data = self.cache.get_auth_data()
        if auth_data is None:
            self.show_first_login()
        else:
            self.show_pin_login()
