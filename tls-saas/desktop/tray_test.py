
import flet as ft
def main(page: ft.Page):
    page.window.prevent_close = True
    def window_event(e):
        print(f"Event: {e.data}")
        if e.data == "close":
            print("Received close signal")
            page.window.visible = False
            page.update()
    page.window.on_event = window_event
    page.add(ft.Text("Hello world"))
ft.app(target=main)

