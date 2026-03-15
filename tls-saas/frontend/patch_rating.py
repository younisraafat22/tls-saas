import codecs

lines = open('../desktop/main.py', 'r', encoding='utf-8').read()

rating_dialog = '''
        def show_rating_dialog(e):
            rating_var = [0]
            
            def set_rating(e):
                val = e.control.data
                rating_var[0] = val
                for i in range(5):
                    stars_row.controls[i].icon = ft.Icons.STAR if i < val else ft.Icons.STAR_BORDER
                page.update()

            def submit_rating(e):
                if rating_var[0] == 0:
                    return
                # Make simple POST
                def _send():
                    try:
                        import requests
                        from config import Config
                        url = f"{Config.API_URL}/metrics/rate"
                        requests.post(url, json={"rating": rating_var[0], "comment": comment_field.value, "source": "desktop"}, timeout=10)
                    except Exception:
                        pass
                import threading
                threading.Thread(target=_send, daemon=True).start()
                close_rating(e)
                self._show_info_snack("Thank you for your feedback!", "#1A3A2A")

            def close_rating(e):
                rating_dlg.open = False
                page.update()

            stars_row = ft.Row(
                [
                    ft.IconButton(icon=ft.Icons.STAR_BORDER, data=i+1, on_click=set_rating, icon_color="#FFD700", icon_size=35)
                    for i in range(5)
                ],
                alignment=ft.MainAxisAlignment.CENTER
            )

            comment_field = ft.TextField(
                multiline=True,
                min_lines=3,
                max_lines=3,
                hint_text="Tell us what you think (optional)",
                border_color="#334444",
                bgcolor="#1A2421",
                color="#E0E0E0"
            )

            rating_dlg = ft.AlertDialog(
                modal=False,
                title=ft.Text("Rate TLS Checker", weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    width=400,
                    content=ft.Column(
                        [
                            ft.Text("How would you rate your experience?", text_align=ft.TextAlign.CENTER, expand=True),
                            stars_row,
                            comment_field
                        ],
                        tight=True,
                        spacing=15
                    )
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=close_rating),
                    ft.TextButton("Submit", on_click=submit_rating),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                bgcolor="#0D1612",
                shape=ft.RoundedRectangleBorder(radius=15),
            )
            page.dialog = rating_dlg
            rating_dlg.open = True
            page.update()
'''

lines = lines.replace('def show_support_dialog(e):', rating_dialog.strip() + '\n\n        def show_support_dialog(e):')

button_str = '''
                                    ft.IconButton(
                                        icon=ft.Icons.STAR,
                                        tooltip="Rate App",
                                        on_click=show_rating_dialog,
                                        icon_color="#FFD700",
                                    ),'''

lines = lines.replace('''                                    ft.IconButton(
                                        icon=ft.Icons.SUPPORT_AGENT,''', button_str.lstrip() + '''\n                                    ft.IconButton(
                                        icon=ft.Icons.SUPPORT_AGENT,''')

with open('../desktop/main.py', 'w', encoding='utf-8') as f:
    f.write(lines)

