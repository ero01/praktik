import yaml
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import datetime

DEFAULT_CONFIG = """
tax_brackets:
  - min_income: 0
    max_income: 1000
    rate: 0.10
  - min_income: 1001
    max_income: 5000
    rate: 0.20
  - min_income: 5001
    rate: 0.30

social_security:
  employee_rate: 0.08
  employer_rate: 0.12
  max_employee_contribution: 400.0
  max_employer_contribution: 600.0

deductions:
  pension:
    type: percentage
    rate: 0.05
  health_insurance:
    type: fixed
    amount: 50.0
"""


class ConfigLoader:
    """
    Класс для загрузки и анализа данных конфигурации
    (налоговые ставки, пороги, типы вычетов).
    """

    def __init__(self, config_path="config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self):
        """
        Загружает конфигурацию из YAML-файла.
        Если файл не найден, использует конфигурацию по умолчанию.
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except yaml.YAMLError as e:
                print(f"Ошибка при анализе файла конфигурации YAML: {e}")
                print("Использование конфигурации по умолчанию.")
                return yaml.safe_load(DEFAULT_CONFIG)
        else:
            print(f"Файл конфигурации '{self.config_path}' не найден. Использование конфигурации по умолчанию.")
            return yaml.safe_load(DEFAULT_CONFIG)

    def get_tax_brackets(self):
        """Возвращает налоговые скобки."""
        return self.config.get('tax_brackets', [])

    def get_social_security_config(self):
        """Возвращает конфигурацию социального страхования."""
        return self.config.get('social_security', {})

    def get_default_deductions(self):
        """Возвращает конфигурацию других вычетов по умолчанию."""
        return self.config.get('deductions', {})

    def save_config(self):
        """Сохраняет текущую конфигурацию в YAML-файл."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f, indent=2, allow_unicode=True)
            messagebox.showinfo("Сохранение конфигурации", "Конфигурация успешно сохранена.")
        except IOError as e:
            messagebox.showerror("Ошибка сохранения", f"Ошибка сохранения файла конфигурации: {e}")


class PayrollResult:
    """
    Инкапсулирует полный результат расчета заработной платы.
    """

    def __init__(self, gross_pay, net_pay, taxes_breakdown, deductions_breakdown, employer_contributions_breakdown):
        self.gross_pay = gross_pay
        self.net_pay = net_pay
        self.taxes_breakdown = taxes_breakdown
        self.deductions_breakdown = deductions_breakdown
        self.employer_contributions_breakdown = employer_contributions_breakdown

    def get_summary(self):
        """
        Возвращает удобочитаемую сводку по заработной плате.
        """
        summary = f"Сводка по расчету заработной платы:\n"
        summary += f"  Валовая заработная плата: {self.gross_pay:.2f}\n"
        summary += f"  Вычеты сотрудника:\n"
        for tax_type, amount in self.taxes_breakdown.items():
            summary += f"    - {tax_type}: {amount:.2f}\n"
        for deduction_type, amount in self.deductions_breakdown.items():
            summary += f"    - {deduction_type}: {amount:.2f}\n"
        summary += f"  Чистая заработная плата: {self.net_pay:.2f}\n"

        if self.employer_contributions_breakdown:
            summary += f"  Взносы работодателя:\n"
            for contrib_type, amount in self.employer_contributions_breakdown.items():
                summary += f"    - {contrib_type}: {amount:.2f}\n"
        return summary


class Employee:
    """
    Представляет отдельного сотрудника с такими атрибутами, как
    основа заработной платы (почасовая, месячная), ставка, тип занятости,
    бонусы, специфические вычеты и налоговые льготы.
    """

    def __init__(self, employee_id, name, base_salary_type, base_salary_value,
                 bonuses=None, custom_deductions=None, hours_worked=None,
                 days_worked=None, tax_exemptions=0.0):
        if base_salary_type not in ['monthly', 'hourly', 'daily']:
            raise ValueError("base_salary_type должен быть 'monthly', 'hourly' или 'daily'.")

        self.employee_id = employee_id
        self.name = name
        self.base_salary_type = base_salary_type
        self.base_salary_value = base_salary_value
        self.bonuses = bonuses if bonuses is not None else []
        self.custom_deductions = custom_deductions if custom_deductions is not None else []
        self.hours_worked = hours_worked
        self.days_worked = days_worked
        self.tax_exemptions = tax_exemptions

    def calculate_gross_pay(self):
        """
        Рассчитывает валовую заработную плату на основе типа и значения базовой зарплаты.
        Включает любые бонусы.
        """
        gross_pay = 0.0
        if self.base_salary_type == 'monthly':
            gross_pay = self.base_salary_value
        elif self.base_salary_type == 'hourly':
            if self.hours_worked is None:
                raise ValueError("Для почасовой оплаты труда необходимо указать часы работы.")
            gross_pay = self.base_salary_value * self.hours_worked
        elif self.base_salary_type == 'daily':
            if self.days_worked is None:
                raise ValueError("Для дневной оплаты труда необходимо указать отработанные дни.")
            gross_pay = self.base_salary_value * self.days_worked

        for bonus in self.bonuses:
            if bonus.get('type') == 'amount':
                gross_pay += bonus.get('value', 0.0)
            elif bonus.get('type') == 'percentage':
                gross_pay += gross_pay * bonus.get('value', 0.0)
        return gross_pay

    def to_dict(self):
        """Преобразует объект Employee в словарь для сериализации."""
        return {
            'employee_id': self.employee_id,
            'name': self.name,
            'base_salary_type': self.base_salary_type,
            'base_salary_value': self.base_salary_value,
            'bonuses': self.bonuses,
            'custom_deductions': self.custom_deductions,
            'hours_worked': self.hours_worked,
            'days_worked': self.days_worked,
            'tax_exemptions': self.tax_exemptions
        }

    @staticmethod
    def from_dict(data):
        """Создает объект Employee из словаря."""
        return Employee(
            employee_id=data['employee_id'],
            name=data.get('name', 'N/A'),
            base_salary_type=data['base_salary_type'],
            base_salary_value=data['base_salary_value'],
            bonuses=data.get('bonuses'),
            custom_deductions=data.get('custom_deductions'),
            hours_worked=data.get('hours_worked'),
            days_worked=data.get('days_worked'),
            tax_exemptions=data.get('tax_exemptions', 0.0)
        )


class PayrollCalculator:
    """
    Центральный класс, отвечающий за оркестровку процесса расчета,
    применение правил и генерацию результатов.
    """

    def __init__(self, config_path="config.yaml"):
        self.config_loader = ConfigLoader(config_path)
        self.tax_brackets = sorted(self.config_loader.get_tax_brackets(), key=lambda x: x.get('min_income', 0))
        self.social_security_config = self.config_loader.get_social_security_config()
        self.default_deductions_config = self.config_loader.get_default_deductions()

    def _calculate_income_tax(self, gross_income, tax_exemptions):
        """
        Рассчитывает подоходный налог на основе прогрессивных налоговых скобок.
        Учитывает налоговые льготы, уменьшающие налогооблагаемую базу.
        """
        taxable_income = max(0.0, gross_income - tax_exemptions)
        total_income_tax = 0.0

        previous_tier_max_income = 0.0

        for bracket in self.tax_brackets:
            min_threshold = bracket.get('min_income', 0.0)
            max_threshold = bracket.get('max_income')
            rate = bracket.get('rate', 0.0)

            if taxable_income <= min_threshold:
                break

            current_tier_upper_bound = min(taxable_income, max_threshold if max_threshold is not None else float('inf'))

            current_tier_lower_bound = max(min_threshold, previous_tier_max_income)

            taxable_amount_in_current_tier = max(0.0, current_tier_upper_bound - current_tier_lower_bound)

            total_income_tax += taxable_amount_in_current_tier * rate

            previous_tier_max_income = max(previous_tier_max_income,
                                           max_threshold if max_threshold is not None else taxable_income)

        return total_income_tax

    def _calculate_employee_social_security_tax(self, gross_income):
        """
        Рассчитывает отчисления на социальное страхование (доля сотрудника).
        """
        employee_rate = self.social_security_config.get('employee_rate', 0.0)
        max_contribution = self.social_security_config.get('max_employee_contribution', float('inf'))

        contribution = gross_income * employee_rate
        return min(contribution, max_contribution)

    def _calculate_employer_social_security_contribution(self, gross_income):
        """
        Рассчитывает отчисления на социальное страхование (доля работодателя).
        """
        employer_rate = self.social_security_config.get('employer_rate', 0.0)
        max_contribution = self.social_security_config.get('max_employer_contribution', float('inf'))

        contribution = gross_income * employer_rate
        return min(contribution, max_contribution)

    def _calculate_other_deductions(self, gross_income, custom_deductions):
        """
        Рассчитывает другие пользовательские вычеты (фиксированные или процентные).
        """
        total_other_deductions = {}

        for ded_name, ded_info in self.default_deductions_config.items():
            amount = 0.0
            if ded_info['type'] == 'fixed':
                amount = ded_info['amount']
            elif ded_info['type'] == 'percentage':
                amount = gross_income * ded_info['rate']
            total_other_deductions[ded_name] = amount

        for ded in custom_deductions:
            ded_name = ded['name']
            amount = 0.0
            if ded['type'] == 'fixed':
                amount = ded['value']
            elif ded['type'] == 'percentage':
                amount = gross_income * ded['value']
            total_other_deductions[ded_name] = amount

        return total_other_deductions

    def calculate_payroll(self, employee):
        """
        Рассчитывает заработную плату для данного сотрудника.
        :param employee: Объект Employee.
        :return: Объект PayrollResult.
        """
        gross_pay = employee.calculate_gross_pay()

        income_tax = self._calculate_income_tax(gross_pay, employee.tax_exemptions)
        employee_social_security_tax = self._calculate_employee_social_security_tax(gross_pay)

        taxes_breakdown = {
            "Подоходный налог": income_tax,
            "Социальное страхование (сотрудник)": employee_social_security_tax,
        }
        total_employee_taxes = sum(taxes_breakdown.values())

        deductions_breakdown = self._calculate_other_deductions(gross_pay, employee.custom_deductions)
        total_other_deductions = sum(deductions_breakdown.values())

        net_pay = gross_pay - total_employee_taxes - total_other_deductions

        employer_social_security_contribution = self._calculate_employer_social_security_contribution(gross_pay)
        employer_contributions_breakdown = {
            "Социальное страхование (работодатель)": employer_social_security_contribution
        }

        return PayrollResult(gross_pay, net_pay, taxes_breakdown,
                             deductions_breakdown, employer_contributions_breakdown)


class ActivityLogger:
    """
    Класс для ведения журнала активности системы.
    """

    def __init__(self, log_file="activity_log.txt"):
        self.log_file = Path(log_file)
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        """Убеждается, что файл журнала существует."""
        if not self.log_file.exists():
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write(f"--- Журнал активности системы расчета заработной платы - {datetime.datetime.now()} ---\n")
            except IOError as e:
                print(f"Ошибка при создании файла журнала: {e}")

    def log_activity(self, activity_description):
        """Записывает активность в журнал."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {activity_description}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except IOError as e:
            print(f"Ошибка при записи в файл журнала: {e}")

    def get_log_content(self):
        """Возвращает все содержимое файла журнала."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "Журнал активности пуст или не найден."
        except IOError as e:
            return f"Ошибка при чтении файла журнала: {e}"


class PayrollSystem:
    """
    Система для управления несколькими сотрудниками и обработки их заработной платы.
    """

    def __init__(self, config_path="config.yaml", employees_data_file="employees.json", log_file="activity_log.txt"):
        self.employees = {}
        self.config_loader = ConfigLoader(config_path)
        self.calculator = PayrollCalculator(config_path)
        self.employees_data_file = Path(employees_data_file)
        self.logger = ActivityLogger(log_file)
        self._load_employees()

    def add_employee(self, employee: Employee):
        """
        Добавляет сотрудника в систему.
        :param employee: Объект Employee.
        """
        action = "обновлен" if employee.employee_id in self.employees else "добавлен"
        self.employees[employee.employee_id] = employee
        self._save_employees()
        self.logger.log_activity(f"Сотрудник {employee.name} (ID: {employee.employee_id}) успешно {action}.")

    def delete_employee(self, employee_id):
        """
        Удаляет сотрудника из системы.
        :param employee_id: ID сотрудника для удаления.
        :return: True, если сотрудник был удален, False в противном случае.
        """
        if employee_id in self.employees:
            employee_name = self.employees[employee_id].name
            del self.employees[employee_id]
            self._save_employees()
            self.logger.log_activity(f"Сотрудник {employee_name} (ID: {employee_id}) успешно удален.")
            messagebox.showinfo("Успех", f"Сотрудник {employee_id} успешно удален.")
            return True
        else:
            messagebox.showerror("Ошибка", f"Сотрудник с ID {employee_id} не найден.")
            return False

    def get_employee(self, employee_id):
        """
        Возвращает объект сотрудника по его ID.
        :param employee_id: ID сотрудника.
        :return: Объект Employee или None, если сотрудник не найден.
        """
        return self.employees.get(employee_id)

    def process_all_payroll(self):
        """
        Обрабатывает расчет заработной платы для всех сотрудников в системе.
        :return: Словарь результатов PayrollResult, где ключ - ID сотрудника.
        """
        all_payroll_results = {}
        if not self.employees:
            self.logger.log_activity("Попытка расчета заработной платы: нет сотрудников в системе.")
            messagebox.showinfo("Информация", "Нет сотрудников для расчета заработной платы.")
            return {}

        self.logger.log_activity("Начат расчет заработной платы для всех сотрудников.")
        for employee_id, employee in self.employees.items():
            try:
                result = self.calculator.calculate_payroll(employee)
                all_payroll_results[employee_id] = result
                self.logger.log_activity(
                    f"Расчет для сотрудника {employee.name} (ID: {employee_id}) завершен. Чистая ЗП: {result.net_pay:.2f}")
            except ValueError as e:
                self.logger.log_activity(f"Ошибка расчета для сотрудника {employee.name} (ID: {employee_id}): {e}")
                messagebox.showerror("Ошибка расчета", f"Ошибка при расчете для сотрудника {employee_id}: {e}")
            except Exception as e:
                self.logger.log_activity(
                    f"Неизвестная ошибка при расчете для сотрудника {employee.name} (ID: {employee_id}): {e}")
                messagebox.showerror("Неизвестная ошибка",
                                     f"Неизвестная ошибка при расчете для сотрудника {employee_id}: {e}")
        self.logger.log_activity("Расчет заработной платы для всех сотрудников завершен.")
        return all_payroll_results

    def _save_employees(self):
        """Сохраняет данные сотрудников в JSON файл."""
        try:
            with open(self.employees_data_file, 'w', encoding='utf-8') as f:
                json.dump([emp.to_dict() for emp in self.employees.values()], f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.log_activity(f"Ошибка сохранения данных сотрудников: {e}")
            messagebox.showerror("Ошибка сохранения", f"Ошибка сохранения данных сотрудников: {e}")

    def _load_employees(self):
        """Загружает данные сотрудников из JSON файла."""
        if self.employees_data_file.exists():
            try:
                with open(self.employees_data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for emp_data in data:
                        employee = Employee.from_dict(emp_data)
                        self.employees[employee.employee_id] = employee
                self.logger.log_activity(f"Данные сотрудников загружены из {self.employees_data_file}.")
            except json.JSONDecodeError as e:
                self.logger.log_activity(
                    f"Ошибка чтения файла данных сотрудников JSON: {e}. Начинаем с пустого списка сотрудников.")
                messagebox.showerror("Ошибка загрузки",
                                     f"Ошибка чтения файла данных сотрудников JSON: {e}\nНачинаем с пустого списка сотрудников.")
            except IOError as e:
                self.logger.log_activity(
                    f"Ошибка загрузки данных сотрудников: {e}. Начинаем с пустого списка сотрудников.")
                messagebox.showerror("Ошибка загрузки",
                                     f"Ошибка загрузки данных сотрудников: {e}\nНачинаем с пустого списка сотрудников.")
        else:
            self.logger.log_activity(
                f"Файл данных сотрудников '{self.employees_data_file}' не найден. Начинаем с пустого списка сотрудников.")
            messagebox.showinfo("Информация",
                                f"Файл данных сотрудников '{self.employees_data_file}' не найден. Начинаем с пустого списка сотрудников.")


class PayrollApp(tk.Tk):
    """
    Класс GUI приложения для расчета заработной платы.
    """

    def __init__(self):
        super().__init__()
        self.title("Система расчета заработной платы")
        self.geometry("1200x800")
        self.config(bg="#f0f0f0")

        config_file_path = Path("config.yaml")
        if not config_file_path.exists():
            with open(config_file_path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_CONFIG)
            print(f"Создан файл конфигурации по умолчанию: {config_file_path}")

        self.payroll_system = PayrollSystem()
        self._create_widgets()
        self._populate_employee_list()

    def _create_widgets(self):
        """Создает все виджеты GUI."""
        s = ttk.Style()
        s.configure('TLabel', font=('Arial', 10), background='#f0f0f0')
        s.configure('TButton', font=('Arial', 10, 'bold'), padding=6)
        s.configure('TEntry', font=('Arial', 10), padding=5)
        s.configure('TCombobox', font=('Arial', 10), padding=5)
        s.configure('TText', font=('Arial', 10), padding=5)
        s.configure('TLabelFrame', font=('Arial', 12, 'bold'), background='#e0e0e0', foreground='blue')
        s.configure('Treeview', font=('Arial', 10), rowheight=25)
        s.configure('Treeview.Heading', font=('Arial', 10, 'bold'))

        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = ttk.Frame(main_pane, padding="15 15 15 15")
        main_pane.add(left_frame, weight=1)

        employee_input_frame = ttk.LabelFrame(left_frame, text="Данные сотрудника", padding="10 10 10 10")
        employee_input_frame.pack(fill=tk.X, pady=5)

        row_idx = 0
        ttk.Label(employee_input_frame, text="ID сотрудника:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        self.employee_id_entry = ttk.Entry(employee_input_frame)
        self.employee_id_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)
        self.employee_id_entry.insert(0, "EMP001")

        row_idx += 1
        ttk.Label(employee_input_frame, text="Имя сотрудника:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        self.employee_name_entry = ttk.Entry(employee_input_frame)
        self.employee_name_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)
        self.employee_name_entry.insert(0, "Иван Иванов")

        row_idx += 1
        ttk.Label(employee_input_frame, text="Тип базовой зарплаты:").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                           padx=5)
        self.base_salary_type_var = tk.StringVar(value="monthly")
        self.base_salary_type_combo = ttk.Combobox(employee_input_frame, textvariable=self.base_salary_type_var,
                                                   values=['monthly', 'hourly', 'daily'], state="readonly")
        self.base_salary_type_combo.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)
        self.base_salary_type_combo.bind("<<ComboboxSelected>>", self._update_salary_type_fields)

        row_idx += 1
        ttk.Label(employee_input_frame, text="Значение базовой зарплаты:").grid(row=row_idx, column=0, sticky="w",
                                                                                pady=2,
                                                                                padx=5)
        self.base_salary_value_entry = ttk.Entry(employee_input_frame)
        self.base_salary_value_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)
        self.base_salary_value_entry.insert(0, "4500.0")

        row_idx += 1
        self.hours_worked_frame = tk.Frame(employee_input_frame)
        ttk.Label(self.hours_worked_frame, text="Отработано часов:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.hours_worked_entry = ttk.Entry(self.hours_worked_frame)
        self.hours_worked_entry.grid(row=0, column=1, sticky="ew", pady=2, padx=5)
        self.hours_worked_entry.insert(0, "160")
        self.hours_worked_frame.grid_columnconfigure(1, weight=1)

        self.days_worked_frame = tk.Frame(employee_input_frame)
        ttk.Label(self.days_worked_frame, text="Отработано дней:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        self.days_worked_entry = ttk.Entry(self.days_worked_frame)
        self.days_worked_entry.grid(row=0, column=1, sticky="ew", pady=2, padx=5)
        self.days_worked_entry.insert(0, "20")
        self.days_worked_frame.grid_columnconfigure(1, weight=1)

        self._update_salary_type_fields()

        row_idx += 1
        ttk.Label(employee_input_frame, text="Налоговые льготы:").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                       padx=5)
        self.tax_exemptions_entry = ttk.Entry(employee_input_frame)
        self.tax_exemptions_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)
        self.tax_exemptions_entry.insert(0, "100.0")

        employee_input_frame.grid_columnconfigure(1, weight=1)

        employee_buttons_frame = ttk.Frame(left_frame, padding="10 0 10 0")
        employee_buttons_frame.pack(fill=tk.X, pady=5)
        employee_buttons_frame.grid_columnconfigure(0, weight=1)
        employee_buttons_frame.grid_columnconfigure(1, weight=1)
        employee_buttons_frame.grid_columnconfigure(2, weight=1)

        ttk.Button(employee_buttons_frame, text="Добавить/Обновить сотрудника", command=self._add_employee_gui).grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
            sticky="ew")
        ttk.Button(employee_buttons_frame, text="Удалить сотрудника", command=self._delete_employee_gui).grid(row=0,
                                                                                                              column=1,
                                                                                                              padx=5,
                                                                                                              pady=5,
                                                                                                              sticky="ew")
        ttk.Button(employee_buttons_frame, text="Редактировать выбранного", command=self._edit_selected_employee).grid(
            row=0,
            column=2,
            padx=5,
            pady=5,
            sticky="ew")

        search_filter_frame = ttk.LabelFrame(left_frame, text="Поиск и Фильтр", padding="10")
        search_filter_frame.pack(fill=tk.X, pady=5)
        search_filter_frame.grid_columnconfigure(1, weight=1)

        ttk.Label(search_filter_frame, text="Поиск (ID/Имя):").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.search_entry = ttk.Entry(search_filter_frame)
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        self.search_entry.bind("<KeyRelease>", self._filter_employees_gui)

        ttk.Label(search_filter_frame, text="Фильтр по типу ЗП:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.filter_salary_type_var = tk.StringVar(value="Все")
        self.filter_salary_type_combo = ttk.Combobox(search_filter_frame, textvariable=self.filter_salary_type_var,
                                                     values=['Все', 'monthly', 'hourly', 'daily'], state="readonly")
        self.filter_salary_type_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=2)
        self.filter_salary_type_combo.bind("<<ComboboxSelected>>", self._filter_employees_gui)

        employee_list_frame = ttk.LabelFrame(left_frame, text="Список сотрудников", padding="10 10 10 10")
        employee_list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        employee_list_frame.grid_rowconfigure(0, weight=1)
        employee_list_frame.grid_columnconfigure(0, weight=1)

        self.employee_tree = ttk.Treeview(employee_list_frame, columns=("ID", "Имя", "Тип", "Зарплата"),
                                          show="headings")
        self.employee_tree.heading("ID", text="ID")
        self.employee_tree.heading("Имя", text="Имя")
        self.employee_tree.heading("Тип", text="Тип ЗП")
        self.employee_tree.heading("Зарплата", text="Значение ЗП")
        self.employee_tree.column("ID", width=70, anchor="center")
        self.employee_tree.column("Имя", width=120, anchor="w")
        self.employee_tree.column("Тип", width=70, anchor="center")
        self.employee_tree.column("Зарплата", width=100, anchor="e")
        self.employee_tree.pack(fill=tk.BOTH, expand=True)

        employee_list_scrollbar = ttk.Scrollbar(employee_list_frame, orient="vertical",
                                                command=self.employee_tree.yview)
        employee_list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.employee_tree.config(yscrollcommand=employee_list_scrollbar.set)

        self.employee_tree.bind("<<TreeviewSelect>>", self._on_employee_select)

        right_frame = ttk.Frame(main_pane, padding="15 15 15 15")
        main_pane.add(right_frame, weight=1)

        self.main_notebook = ttk.Notebook(right_frame)
        self.main_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        payroll_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(payroll_tab, text="Расчеты")
        self._create_payroll_tab_content(payroll_tab)

        reports_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(reports_tab, text="Отчеты")
        self._create_reports_tab_content(reports_tab)

        activity_log_tab = ttk.Frame(self.main_notebook)
        self.main_notebook.add(activity_log_tab, text="Журнал Активности")
        self._create_activity_log_tab_content(activity_log_tab)

    def _create_payroll_tab_content(self, parent_frame):
        """Создает содержимое вкладки "Расчеты"."""
        parent_frame.grid_rowconfigure(0, weight=0)
        parent_frame.grid_rowconfigure(1, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(1, weight=1)

        calc_buttons_frame = ttk.Frame(parent_frame, padding="10 0 10 0")
        calc_buttons_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        calc_buttons_frame.grid_columnconfigure(0, weight=1)
        calc_buttons_frame.grid_columnconfigure(1, weight=1)
        calc_buttons_frame.grid_columnconfigure(2, weight=1)

        ttk.Button(calc_buttons_frame, text="Рассчитать зарплату (все)", command=self._calculate_all_payroll_gui).grid(
            row=0,
            column=0,
            padx=5,
            pady=5,
            sticky="ew")
        ttk.Button(calc_buttons_frame, text="Экспорт результатов в CSV", command=self._export_payroll_results_csv).grid(
            row=0,
            column=1,
            padx=5,
            pady=5,
            sticky="ew")
        ttk.Button(calc_buttons_frame, text="Редактировать конфигурацию", command=self._open_config_editor_window).grid(
            row=0,
            column=2,
            padx=5,
            pady=5,
            sticky="ew")

        result_frame = ttk.LabelFrame(parent_frame, text="Результаты расчета", padding="10 10 10 10")
        result_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        result_frame.grid_rowconfigure(0, weight=1)
        result_frame.grid_columnconfigure(0, weight=1)

        self.payroll_summary_text = tk.Text(result_frame, wrap="word", height=15, width=80)
        self.payroll_summary_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        scrollbar = ttk.Scrollbar(result_frame, orient="vertical", command=self.payroll_summary_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.payroll_summary_text.config(yscrollcommand=scrollbar.set)

    def _create_reports_tab_content(self, parent_frame):
        """Создает содержимое вкладки "Отчеты"."""
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(1, weight=1)

        reports_text_frame = ttk.LabelFrame(parent_frame, text="Сводные Отчеты", padding="10")
        reports_text_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)
        reports_text_frame.grid_rowconfigure(0, weight=1)
        reports_text_frame.grid_columnconfigure(0, weight=1)

        self.reports_text = tk.Text(reports_text_frame, wrap="word", height=20)
        self.reports_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        reports_scrollbar = ttk.Scrollbar(reports_text_frame, orient="vertical", command=self.reports_text.yview)
        reports_scrollbar.grid(row=0, column=1, sticky="ns")
        self.reports_text.config(yscrollcommand=reports_scrollbar.set)

        reports_buttons_frame = ttk.Frame(parent_frame, padding="10")
        reports_buttons_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=5)
        reports_buttons_frame.grid_columnconfigure(0, weight=1)
        reports_buttons_frame.grid_columnconfigure(1, weight=1)

        ttk.Button(reports_buttons_frame, text="Сгенерировать сводный отчет",
                   command=self._generate_summary_report).grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Button(reports_buttons_frame, text="Экспорт отчета в CSV", command=self._export_summary_report_csv).grid(
            row=0, column=1, padx=5, pady=5, sticky="ew")

    def _create_activity_log_tab_content(self, parent_frame):
        """Создает содержимое вкладки "Журнал Активности"."""
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(parent_frame, text="Системный Журнал Активности", padding="10")
        log_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.activity_log_text = tk.Text(log_frame, wrap="word", height=20, state="disabled")
        self.activity_log_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.activity_log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.activity_log_text.config(yscrollcommand=log_scrollbar.set)

        ttk.Button(parent_frame, text="Обновить Журнал", command=self._refresh_activity_log).grid(row=1, column=0,
                                                                                                  pady=5)
        self._refresh_activity_log()

    def _refresh_activity_log(self):
        """Обновляет содержимое текстового поля журнала активности."""
        log_content = self.payroll_system.logger.get_log_content()
        self.activity_log_text.config(state="normal")
        self.activity_log_text.delete(1.0, tk.END)
        self.activity_log_text.insert(tk.END, log_content)
        self.activity_log_text.config(state="disabled")

    def _generate_summary_report(self):
        """Генерирует и отображает сводный отчет."""
        self.reports_text.delete(1.0, tk.END)

        all_results = self.payroll_system.process_all_payroll()

        if not all_results:
            self.reports_text.insert(tk.END, "Нет данных для генерации отчета.")
            return

        total_gross_pay = sum(res.gross_pay for res in all_results.values())
        total_net_pay = sum(res.net_pay for res in all_results.values())
        total_employee_taxes = sum(sum(res.taxes_breakdown.values()) for res in all_results.values())
        total_employee_deductions = sum(sum(res.deductions_breakdown.values()) for res in all_results.values())
        total_employer_contributions = sum(
            sum(res.employer_contributions_breakdown.values()) for res in all_results.values())

        report_summary = "--- Сводный Отчет по Заработной Плате ---\n\n"
        report_summary += f"Общее количество сотрудников: {len(self.payroll_system.employees)}\n"
        report_summary += f"Общая валовая заработная плата: {total_gross_pay:.2f}\n"
        report_summary += f"Общая чистая заработная плата: {total_net_pay:.2f}\n"
        report_summary += f"Общие вычеты сотрудников (налоги, пенсионные и т.д.): {total_employee_taxes + total_employee_deductions:.2f}\n"
        report_summary += f"Общие взносы работодателя: {total_employer_contributions:.2f}\n\n"
        report_summary += "--- Детали по вычетам сотрудников ---\n"

        aggregated_taxes = {}
        for res in all_results.values():
            for tax_type, amount in res.taxes_breakdown.items():
                aggregated_taxes[tax_type] = aggregated_taxes.get(tax_type, 0) + amount
            for ded_type, amount in res.deductions_breakdown.items():
                aggregated_taxes[ded_type] = aggregated_taxes.get(ded_type, 0) + amount

        for name, amount in aggregated_taxes.items():
            report_summary += f"  - {name}: {amount:.2f}\n"

        self.reports_text.insert(tk.END, report_summary)
        messagebox.showinfo("Отчет", "Сводный отчет сгенерирован.")
        self.payroll_system.logger.log_activity("Сводный отчет по заработной плате сгенерирован.")

    def _export_summary_report_csv(self):
        """Экспортирует сводный отчет в CSV файл."""
        all_results = self.payroll_system.process_all_payroll()
        if not all_results:
            messagebox.showwarning("Предупреждение", "Нет данных для экспорта сводного отчета.")
            return

        try:
            file_path = simpledialog.askstring("Экспорт сводного отчета в CSV",
                                               "Введите имя файла (например, summary_report.csv):")
            if not file_path:
                return

            if not file_path.endswith(".csv"):
                file_path += ".csv"

            total_gross_pay = sum(res.gross_pay for res in all_results.values())
            total_net_pay = sum(res.net_pay for res in all_results.values())
            total_employee_taxes = sum(sum(res.taxes_breakdown.values()) for res in all_results.values())
            total_employee_deductions = sum(sum(res.deductions_breakdown.values()) for res in all_results.values())
            total_employer_contributions = sum(
                sum(res.employer_contributions_breakdown.values()) for res in all_results.values())

            aggregated_taxes = {}
            for res in all_results.values():
                for tax_type, amount in res.taxes_breakdown.items():
                    aggregated_taxes[tax_type] = aggregated_taxes.get(tax_type, 0) + amount
                for ded_type, amount in res.deductions_breakdown.items():
                    aggregated_taxes[ded_type] = aggregated_taxes.get(ded_type, 0) + amount

            tax_ded_columns = sorted(list(aggregated_taxes.keys()))
            header = ["Метрика", "Значение"] + tax_ded_columns

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(",".join(header) + "\n")

                f.write(
                    f"Общее количество сотрудников,{len(self.payroll_system.employees)},{','.join(['' for _ in tax_ded_columns])}\n")
                f.write(
                    f"Общая валовая заработная плата,{total_gross_pay:.2f},{','.join(['' for _ in tax_ded_columns])}\n")
                f.write(
                    f"Общая чистая заработная плата,{total_net_pay:.2f},{','.join(['' for _ in tax_ded_columns])}\n")
                f.write(
                    f"Общие вычеты сотрудников (налоги, пенсионные и т.д.),{total_employee_taxes + total_employee_deductions:.2f},{','.join(['' for _ in tax_ded_columns])}\n")
                f.write(
                    f"Общие взносы работодателя,{total_employer_contributions:.2f},{','.join(['' for _ in tax_ded_columns])}\n")

                f.write("Детали по вычетам сотрудников,,{}\n".format(','.join(['' for _ in tax_ded_columns])))
                for col in tax_ded_columns:
                    f.write(f"  {col},{aggregated_taxes.get(col, 0):.2f},{','.join(['' for _ in tax_ded_columns])}\n")

            messagebox.showinfo("Экспорт завершен", f"Сводный отчет успешно экспортирован в '{file_path}'.")
            self.payroll_system.logger.log_activity(f"Сводный отчет экспортирован в CSV: '{file_path}'.")
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Произошла ошибка при экспорте: {e}")
            self.payroll_system.logger.log_activity(f"Ошибка экспорта сводного отчета в CSV: {e}")

    def _update_salary_type_fields(self, event=None):
        """Обновляет видимость полей часов/дней в зависимости от типа зарплаты."""
        salary_type = self.base_salary_type_var.get()
        if salary_type == 'hourly':
            self.hours_worked_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=2, padx=5)
            self.days_worked_frame.grid_remove()
        elif salary_type == 'daily':
            self.days_worked_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=2, padx=5)
            self.hours_worked_frame.grid_remove()
        else:
            self.hours_worked_frame.grid_remove()
            self.days_worked_frame.grid_remove()

    def _get_input_value(self, entry_widget, type_converter, field_name, allow_empty=False):
        """Вспомогательная функция для безопасного получения значений из Entry."""
        value_str = entry_widget.get().strip()
        if not value_str:
            if allow_empty:
                return None
            else:
                raise ValueError(f"Поле '{field_name}' не может быть пустым.")
        try:
            return type_converter(value_str)
        except ValueError:
            raise ValueError(f"Некорректное значение для '{field_name}'. Пожалуйста, введите число.")

    def _add_employee_gui(self):
        """Обработчик кнопки для добавления/обновления сотрудника."""
        try:
            employee_id = self.employee_id_entry.get().strip()
            if not employee_id:
                messagebox.showerror("Ошибка ввода", "ID сотрудника не может быть пустым.")
                return

            employee_name = self.employee_name_entry.get().strip()
            if not employee_name:
                messagebox.showerror("Ошибка ввода", "Имя сотрудника не может быть пустым.")
                return

            base_salary_type = self.base_salary_type_var.get()
            base_salary_value = self._get_input_value(self.base_salary_value_entry, float, "Базовая зарплата")
            if base_salary_value < 0:
                raise ValueError("Базовая зарплата не может быть отрицательной.")

            hours_worked = None
            if base_salary_type == 'hourly':
                hours_worked = self._get_input_value(self.hours_worked_entry, int, "Отработано часов")
                if hours_worked is not None and hours_worked < 0:
                    raise ValueError("Отработано часов не может быть отрицательным.")

            days_worked = None
            if base_salary_type == 'daily':
                days_worked = self._get_input_value(self.days_worked_entry, int, "Отработано дней")
                if days_worked is not None and days_worked < 0:
                    raise ValueError("Отработано дней не может быть отрицательным.")

            tax_exemptions = self._get_input_value(self.tax_exemptions_entry, float, "Налоговые льготы",
                                                   allow_empty=True) or 0.0
            if tax_exemptions < 0:
                raise ValueError("Налоговые льготы не могут быть отрицательными.")

            bonuses = []
            custom_deductions = []

            existing_employee = self.payroll_system.get_employee(employee_id)
            if existing_employee:
                bonuses = existing_employee.bonuses
                custom_deductions = existing_employee.custom_deductions

            employee = Employee(employee_id, employee_name, base_salary_type, base_salary_value,
                                bonuses, custom_deductions, hours_worked, days_worked, tax_exemptions)
            self.payroll_system.add_employee(employee)
            messagebox.showinfo("Успех", f"Сотрудник {employee_id} ({employee_name}) успешно добавлен/обновлен.")
            self._populate_employee_list()
            self._clear_input_fields()

        except ValueError as e:
            messagebox.showerror("Ошибка ввода", str(e))
        except Exception as e:
            messagebox.showerror("Неизвестная ошибка", f"Произошла ошибка: {e}")

    def _delete_employee_gui(self):
        """Обработчик кнопки для удаления сотрудника."""
        selected_item = self.employee_tree.selection()
        if not selected_item:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите сотрудника для удаления.")
            return

        employee_id = self.employee_tree.item(selected_item, "values")[0]
        if messagebox.askyesno("Подтверждение удаления",
                               f"Вы уверены, что хотите удалить сотрудника с ID: {employee_id}?"):
            if self.payroll_system.delete_employee(employee_id):
                self._populate_employee_list()
                self._clear_input_fields()

    def _edit_selected_employee(self):
        """Открывает окно для детального редактирования выбранного сотрудника."""
        selected_item = self.employee_tree.selection()
        if not selected_item:
            messagebox.showwarning("Предупреждение", "Пожалуйста, выберите сотрудника для редактирования.")
            return

        employee_id = self.employee_tree.item(selected_item, "values")[0]
        employee = self.payroll_system.get_employee(employee_id)

        if employee:
            self._open_employee_details_window(employee)
        else:
            messagebox.showerror("Ошибка", "Выбранный сотрудник не найден.")

    def _open_employee_details_window(self, employee):
        """Создает и отображает окно с деталями сотрудника для редактирования."""
        details_window = tk.Toplevel(self)
        details_window.title(f"Детали сотрудника: {employee.employee_id} ({employee.name})")
        details_window.transient(self)
        details_window.grab_set()

        details_frame = ttk.LabelFrame(details_window, text="Редактирование данных сотрудника", padding="10")
        details_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        row_idx = 0
        ttk.Label(details_frame, text="ID сотрудника:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        id_entry = ttk.Entry(details_frame, state='readonly')
        id_entry.insert(0, employee.employee_id)
        id_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Имя сотрудника:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        name_entry = ttk.Entry(details_frame)
        name_entry.insert(0, employee.name)
        name_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Тип ЗП:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        base_salary_type_var = tk.StringVar(value=employee.base_salary_type)
        base_salary_type_combo = ttk.Combobox(details_frame, textvariable=base_salary_type_var,
                                              values=['monthly', 'hourly', 'daily'], state="readonly")
        base_salary_type_combo.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Значение ЗП:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        base_salary_value_entry = ttk.Entry(details_frame)
        base_salary_value_entry.insert(0, str(employee.base_salary_value))
        base_salary_value_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Отработано часов:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        hours_worked_entry = ttk.Entry(details_frame)
        hours_worked_entry.insert(0, str(employee.hours_worked if employee.hours_worked is not None else ""))
        hours_worked_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Отработано дней:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        days_worked_entry = ttk.Entry(details_frame)
        days_worked_entry.insert(0, str(employee.days_worked if employee.days_worked is not None else ""))
        days_worked_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(details_frame, text="Налоговые льготы:").grid(row=row_idx, column=0, sticky="w", pady=2, padx=5)
        tax_exemptions_entry = ttk.Entry(details_frame)
        tax_exemptions_entry.insert(0, str(employee.tax_exemptions))
        tax_exemptions_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        bonuses_frame = ttk.LabelFrame(details_frame, text="Бонусы", padding="5")
        bonuses_frame.grid(row=row_idx + 1, column=0, columnspan=2, sticky="ew", pady=5)
        bonuses_tree = ttk.Treeview(bonuses_frame, columns=("Название", "Тип", "Значение"), show="headings", height=3)
        bonuses_tree.heading("Название", text="Название")
        bonuses_tree.heading("Тип", text="Тип")
        bonuses_tree.heading("Значение", text="Значение")
        bonuses_tree.column("Название", width=150)
        bonuses_tree.column("Тип", width=80)
        bonuses_tree.column("Значение", width=100)
        bonuses_tree.pack(fill=tk.BOTH, expand=True)

        for bonus in employee.bonuses:
            bonuses_tree.insert("", "end",
                                values=(bonus.get('name', ''), bonus.get('type', ''), bonus.get('value', '')))

        def add_bonus():
            name = simpledialog.askstring("Добавить бонус", "Название бонуса:")
            if name:
                bonus_type = simpledialog.askstring("Добавить бонус", "Тип (amount/percentage):", initialvalue="amount")
                if bonus_type in ["amount", "percentage"]:
                    try:
                        value = simpledialog.askfloat("Добавить бонус", "Значение:")
                        if value is not None:
                            if bonus_type == 'percentage' and (value < 0 or value > 1):
                                messagebox.showerror("Ошибка", "Процент бонуса должен быть между 0 и 1.")
                                return
                            employee.bonuses.append({'name': name, 'type': bonus_type, 'value': value})
                            bonuses_tree.insert("", "end", values=(name, bonus_type, value))
                    except (TypeError, ValueError):
                        messagebox.showerror("Ошибка", "Некорректное значение.")
                else:
                    messagebox.showerror("Ошибка", "Некорректный тип бонуса.")

        def remove_bonus():
            selected_items = bonuses_tree.selection()
            if not selected_items:
                messagebox.showwarning("Предупреждение", "Выберите бонус для удаления.")
                return
            for item in selected_items:
                values = bonuses_tree.item(item, "values")
                name_to_remove = values[0]
                type_to_remove = values[1]
                value_to_remove = values[2]
                employee.bonuses = [b for b in employee.bonuses if not (b.get('name') == name_to_remove and
                                                                        b.get('type') == type_to_remove and
                                                                        b.get('value') == value_to_remove)]
                bonuses_tree.delete(item)

        bonus_buttons_frame = ttk.Frame(bonuses_frame)
        bonus_buttons_frame.pack(pady=5)
        ttk.Button(bonus_buttons_frame, text="Добавить бонус", command=add_bonus).grid(row=0, column=0, padx=5)
        ttk.Button(bonus_buttons_frame, text="Удалить бонус", command=remove_bonus).grid(row=0, column=1, padx=5)

        deductions_frame = ttk.LabelFrame(details_frame, text="Пользовательские вычеты", padding="5")
        deductions_frame.grid(row=row_idx + 2, column=0, columnspan=2, sticky="ew", pady=5)
        deductions_tree = ttk.Treeview(deductions_frame, columns=("Название", "Тип", "Значение"), show="headings",
                                       height=3)
        deductions_tree.heading("Название", text="Название")
        deductions_tree.heading("Тип", text="Тип")
        deductions_tree.heading("Значение", text="Значение")
        deductions_tree.column("Название", width=150)
        deductions_tree.column("Тип", width=80)
        deductions_tree.column("Значение", width=100)
        deductions_tree.pack(fill=tk.BOTH, expand=True)

        for ded in employee.custom_deductions:
            deductions_tree.insert("", "end", values=(ded.get('name', ''), ded.get('type', ''), ded.get('value', '')))

        def add_deduction():
            name = simpledialog.askstring("Добавить вычет", "Название вычета:")
            if name:
                deduction_type = simpledialog.askstring("Добавить вычет", "Тип (fixed/percentage):",
                                                        initialvalue="fixed")
                if deduction_type in ["fixed", "percentage"]:
                    try:
                        value = simpledialog.askfloat("Добавить вычет", "Значение:")
                        if value is not None:
                            if deduction_type == 'percentage' and (value < 0 or value > 1):
                                messagebox.showerror("Ошибка", "Процент вычета должен быть между 0 и 1.")
                                return
                            employee.custom_deductions.append({'name': name, 'type': deduction_type, 'value': value})
                            deductions_tree.insert("", "end", values=(name, deduction_type, value))
                    except (TypeError, ValueError):
                        messagebox.showerror("Ошибка", "Некорректное значение.")
                else:
                    messagebox.showerror("Ошибка", "Некорректный тип вычета.")

        def remove_deduction():
            selected_items = deductions_tree.selection()
            if not selected_items:
                messagebox.showwarning("Предупреждение", "Выберите вычет для удаления.")
                return
            for item in selected_items:
                values = deductions_tree.item(item, "values")
                name_to_remove = values[0]
                type_to_remove = values[1]
                value_to_remove = values[2]
                employee.custom_deductions = [d for d in employee.custom_deductions if
                                              not (d.get('name') == name_to_remove and
                                                   d.get('type') == type_to_remove and
                                                   d.get('value') == value_to_remove)]
                deductions_tree.delete(item)

        deduction_buttons_frame = ttk.Frame(deductions_frame)
        deduction_buttons_frame.pack(pady=5)
        ttk.Button(deduction_buttons_frame, text="Добавить вычет", command=add_deduction).grid(row=0, column=0, padx=5)
        ttk.Button(deduction_buttons_frame, text="Удалить вычет", command=remove_deduction).grid(row=0, column=1,
                                                                                                 padx=5)

        def save_and_close():
            try:
                employee.name = name_entry.get().strip()
                if not employee.name:
                    raise ValueError("Имя сотрудника не может быть пустым.")

                employee.base_salary_type = base_salary_type_var.get()
                employee.base_salary_value = float(base_salary_value_entry.get())
                if employee.base_salary_value < 0:
                    raise ValueError("Базовая зарплата не может быть отрицательной.")

                hours_worked_str = hours_worked_entry.get().strip()
                employee.hours_worked = int(hours_worked_str) if hours_worked_str else None
                if employee.hours_worked is not None and employee.hours_worked < 0:
                    raise ValueError("Отработано часов не может быть отрицательным.")

                days_worked_str = days_worked_entry.get().strip()
                employee.days_worked = int(days_worked_str) if days_worked_str else None
                if employee.days_worked is not None and employee.days_worked < 0:
                    raise ValueError("Отработано дней не может быть отрицательным.")

                employee.tax_exemptions = float(tax_exemptions_entry.get())
                if employee.tax_exemptions < 0:
                    raise ValueError("Налоговые льготы не могут быть отрицательными.")

                self.payroll_system.add_employee(employee)
                messagebox.showinfo("Успех",
                                    f"Данные сотрудника {employee.employee_id} ({employee.name}) успешно обновлены.")
                self._populate_employee_list()
                details_window.destroy()
            except ValueError as e:
                messagebox.showerror("Ошибка сохранения", str(e))
            except Exception as e:
                messagebox.showerror("Неизвестная ошибка", f"Ошибка при сохранении: {e}")

        save_cancel_frame = ttk.Frame(details_frame, padding="10")
        save_cancel_frame.grid(row=row_idx + 3, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Button(save_cancel_frame, text="Сохранить", command=save_and_close).pack(side=tk.LEFT, padx=5)
        ttk.Button(save_cancel_frame, text="Отмена", command=details_window.destroy).pack(side=tk.LEFT, padx=5)

        details_window.protocol("WM_DELETE_WINDOW", details_window.destroy)
        details_window.focus_set()

    def _open_config_editor_window(self):
        """Открывает окно для редактирования конфигурации."""
        config_window = tk.Toplevel(self)
        config_window.title("Редактирование конфигурации")
        config_window.transient(self)
        config_window.grab_set()

        config_frame = ttk.LabelFrame(config_window, text="Настройки конфигурации", padding="10")
        config_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(config_frame)
        notebook.pack(pady=5, fill=tk.BOTH, expand=True)

        tax_brackets_tab = ttk.Frame(notebook)
        notebook.add(tax_brackets_tab, text="Налоговые скобки")
        tax_brackets_tab.grid_columnconfigure(0, weight=1)
        tax_brackets_tab.grid_rowconfigure(0, weight=1)

        tax_tree = ttk.Treeview(tax_brackets_tab, columns=("min", "max", "rate"), show="headings", height=8)
        tax_tree.heading("min", text="Мин. доход")
        tax_tree.heading("max", text="Макс. доход")
        tax_tree.heading("rate", text="Ставка (%)")
        tax_tree.column("min", width=100, anchor="e")
        tax_tree.column("max", width=100, anchor="e")
        tax_tree.column("rate", width=80, anchor="e")
        tax_tree.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        tax_tree_scrollbar = ttk.Scrollbar(tax_brackets_tab, orient="vertical", command=tax_tree.yview)
        tax_tree_scrollbar.grid(row=0, column=1, sticky="ns")
        tax_tree.config(yscrollcommand=tax_tree_scrollbar.set)

        def populate_tax_tree():
            for item in tax_tree.get_children():
                tax_tree.delete(item)
            sorted_brackets = sorted(self.payroll_system.config_loader.get_tax_brackets(),
                                     key=lambda x: x.get('min_income', 0))
            for bracket in sorted_brackets:
                max_income = str(bracket.get('max_income', '')) if bracket.get('max_income') is not None else ""
                tax_tree.insert("", "end", values=(
                f"{bracket.get('min_income'):.2f}", max_income, f"{bracket.get('rate') * 100:.2f}"))

        populate_tax_tree()

        def add_tax_bracket():
            try:
                min_income = simpledialog.askfloat("Добавить скобку", "Минимальный доход:")
                if min_income is None: return
                max_income_str = simpledialog.askstring("Добавить скобку",
                                                        "Максимальный доход (оставьте пустым для безлимита):")
                max_income = float(max_income_str) if max_income_str else None
                rate = simpledialog.askfloat("Добавить скобку", "Ставка (например, 0.10 для 10%):")
                if rate is None: return

                if not (0 <= rate <= 1):
                    messagebox.showerror("Ошибка", "Ставка должна быть от 0 до 1.")
                    return

                new_bracket = {'min_income': min_income, 'rate': rate}
                if max_income is not None:
                    new_bracket['max_income'] = max_income

                self.payroll_system.config_loader.config['tax_brackets'].append(new_bracket)
                self.payroll_system.config_loader.config['tax_brackets'] = sorted(
                    self.payroll_system.config_loader.config['tax_brackets'],
                    key=lambda x: x.get('min_income', 0)
                )
                populate_tax_tree()
                self.payroll_system.logger.log_activity(
                    f"Добавлена налоговая скобка: Мин. {min_income}, Макс. {max_income}, Ставка {rate * 100:.2f}%.")
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректный ввод. Введите числовые значения.")

        def remove_tax_bracket():
            selected_item = tax_tree.selection()
            if not selected_item:
                messagebox.showwarning("Предупреждение", "Выберите налоговую скобку для удаления.")
                return

            values = tax_tree.item(selected_item, "values")
            min_inc = float(values[0])
            max_inc_str = values[1]
            max_inc = float(max_inc_str) if max_inc_str else None
            rate_val = float(values[2]) / 100

            current_brackets = self.payroll_system.config_loader.config['tax_brackets']
            new_brackets = []
            found = False
            for bracket in current_brackets:
                current_max_income = bracket.get('max_income')
                if bracket.get('min_income') == min_inc and \
                        ((current_max_income is None and max_inc is None) or \
                         (current_max_income is not None and max_inc is not None and current_max_income == max_inc)) and \
                        bracket.get('rate') == rate_val:
                    found = True
                else:
                    new_brackets.append(bracket)

            if found:
                self.payroll_system.config_loader.config['tax_brackets'] = new_brackets
                populate_tax_tree()
                messagebox.showinfo("Успех", "Налоговая скобка удалена.")
                self.payroll_system.logger.log_activity(
                    f"Удалена налоговая скобка: Мин. {min_inc}, Макс. {max_inc}, Ставка {rate_val * 100:.2f}%.")
            else:
                messagebox.showerror("Ошибка", "Не удалось найти и удалить налоговую скобку.")

        tax_buttons_frame = ttk.Frame(tax_brackets_tab)
        tax_buttons_frame.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(tax_buttons_frame, text="Добавить", command=add_tax_bracket).pack(side=tk.LEFT, padx=5)
        ttk.Button(tax_buttons_frame, text="Удалить", command=remove_tax_bracket).pack(side=tk.LEFT, padx=5)

        social_security_tab = ttk.Frame(notebook)
        notebook.add(social_security_tab, text="Социальное страхование")
        social_security_tab.grid_columnconfigure(1, weight=1)

        ss_config = self.payroll_system.config_loader.get_social_security_config()

        row_idx = 0
        ttk.Label(social_security_tab, text="Ставка сотрудника (%):").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                           padx=5)
        employee_rate_entry = ttk.Entry(social_security_tab)
        employee_rate_entry.insert(0, str(ss_config.get('employee_rate', 0.0) * 100))
        employee_rate_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(social_security_tab, text="Макс. взнос сотрудника:").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                            padx=5)
        max_employee_contrib_entry = ttk.Entry(social_security_tab)
        max_employee_contrib_entry.insert(0, str(ss_config.get('max_employee_contribution', 0.0)))
        max_employee_contrib_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(social_security_tab, text="Ставка работодателя (%):").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                             padx=5)
        employer_rate_entry = ttk.Entry(social_security_tab)
        employer_rate_entry.insert(0, str(ss_config.get('employer_rate', 0.0) * 100))
        employer_rate_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        row_idx += 1
        ttk.Label(social_security_tab, text="Макс. взнос работодателя:").grid(row=row_idx, column=0, sticky="w", pady=2,
                                                                              padx=5)
        max_employer_contrib_entry = ttk.Entry(social_security_tab)
        max_employer_contrib_entry.insert(0, str(ss_config.get('max_employer_contribution', 0.0)))
        max_employer_contrib_entry.grid(row=row_idx, column=1, sticky="ew", pady=2, padx=5)

        default_deductions_tab = ttk.Frame(notebook)
        notebook.add(default_deductions_tab, text="Вычеты по умолчанию")
        default_deductions_tab.grid_columnconfigure(0, weight=1)
        default_deductions_tab.grid_rowconfigure(0, weight=1)

        deductions_tree_config = ttk.Treeview(default_deductions_tab, columns=("Название", "Тип", "Значение"),
                                              show="headings", height=8)
        deductions_tree_config.heading("Название", text="Название")
        deductions_tree_config.heading("Тип", text="Тип")
        deductions_tree_config.heading("Значение", text="Значение")
        deductions_tree_config.column("Название", width=150)
        deductions_tree_config.column("Тип", width=80)
        deductions_tree_config.column("Значение", width=100)
        deductions_tree_config.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        ded_config_scrollbar = ttk.Scrollbar(default_deductions_tab, orient="vertical",
                                             command=deductions_tree_config.yview)
        ded_config_scrollbar.grid(row=0, column=1, sticky="ns")
        deductions_tree_config.config(yscrollcommand=ded_config_scrollbar.set)

        def populate_deductions_tree():
            for item in deductions_tree_config.get_children():
                deductions_tree_config.delete(item)
            for ded_name, ded_info in self.payroll_system.config_loader.get_default_deductions().items():
                value_display = f"{ded_info.get('amount', 0):.2f}" if ded_info.get(
                    'type') == 'fixed' else f"{ded_info.get('rate', 0) * 100:.2f}%"
                deductions_tree_config.insert("", "end", values=(ded_name, ded_info.get('type', ''), value_display))

        populate_deductions_tree()

        def add_default_deduction():
            name = simpledialog.askstring("Добавить вычет по умолчанию", "Название вычета:")
            if name:
                deduction_type = simpledialog.askstring("Добавить вычет по умолчанию", "Тип (fixed/percentage):",
                                                        initialvalue="fixed")
                if deduction_type in ["fixed", "percentage"]:
                    try:
                        value = simpledialog.askfloat("Добавить вычет по умолчанию", "Значение (для % от 0 до 1):")
                        if value is not None:
                            if deduction_type == 'percentage' and (value < 0 or value > 1):
                                messagebox.showerror("Ошибка", "Процент вычета должен быть между 0 и 1.")
                                return

                            if name in self.payroll_system.config_loader.config['deductions']:
                                messagebox.showwarning("Предупреждение",
                                                       f"Вычет '{name}' уже существует и будет обновлен.")

                            if deduction_type == 'fixed':
                                self.payroll_system.config_loader.config['deductions'][name] = {'type': deduction_type,
                                                                                                'amount': value}
                            else:
                                self.payroll_system.config_loader.config['deductions'][name] = {'type': deduction_type,
                                                                                                'rate': value}
                            populate_deductions_tree()
                            self.payroll_system.logger.log_activity(f"Добавлен/обновлен вычет по умолчанию '{name}'.")
                    except (TypeError, ValueError):
                        messagebox.showerror("Ошибка", "Некорректное значение.")
                else:
                    messagebox.showerror("Ошибка", "Некорректный тип вычета.")

        def remove_default_deduction():
            selected_item = deductions_tree_config.selection()
            if not selected_item:
                messagebox.showwarning("Предупреждение", "Выберите вычет для удаления.")
                return

            name_to_remove = deductions_tree_config.item(selected_item, "values")[0]
            if name_to_remove in self.payroll_system.config_loader.config['deductions']:
                del self.payroll_system.config_loader.config['deductions'][name_to_remove]
                populate_deductions_tree()
                messagebox.showinfo("Успех", f"Вычет '{name_to_remove}' удален.")
                self.payroll_system.logger.log_activity(f"Удален вычет по умолчанию '{name_to_remove}'.")
            else:
                messagebox.showerror("Ошибка", "Не удалось найти и удалить вычет.")

        deduction_buttons_frame_config = ttk.Frame(default_deductions_tab)
        deduction_buttons_frame_config.grid(row=1, column=0, columnspan=2, pady=5)
        ttk.Button(deduction_buttons_frame_config, text="Добавить", command=add_default_deduction).pack(side=tk.LEFT,
                                                                                                        padx=5)
        ttk.Button(deduction_buttons_frame_config, text="Удалить", command=remove_default_deduction).pack(side=tk.LEFT,
                                                                                                          padx=5)

        def save_config_and_close():
            try:
                self.payroll_system.config_loader.config['social_security']['employee_rate'] = float(
                    employee_rate_entry.get()) / 100
                self.payroll_system.config_loader.config['social_security']['max_employee_contribution'] = float(
                    max_employee_contrib_entry.get())
                self.payroll_system.config_loader.config['social_security']['employer_rate'] = float(
                    employer_rate_entry.get()) / 100
                self.payroll_system.config_loader.config['social_security']['max_employer_contribution'] = float(
                    max_employer_contrib_entry.get())

                if not (0 <= self.payroll_system.config_loader.config['social_security']['employee_rate'] <= 1 and
                        0 <= self.payroll_system.config_loader.config['social_security']['employer_rate'] <= 1):
                    raise ValueError("Ставки социального страхования должны быть от 0 до 1 (0% до 100%).")

                self.payroll_system.config_loader.save_config()
                self.payroll_system.calculator = PayrollCalculator(self.payroll_system.config_loader.config_path)
                self.payroll_system.logger.log_activity("Конфигурация системы успешно обновлена.")
                config_window.destroy()
            except ValueError as e:
                messagebox.showerror("Ошибка ввода", str(e))
                self.payroll_system.logger.log_activity(f"Ошибка ввода при обновлении конфигурации: {e}")
            except Exception as e:
                messagebox.showerror("Ошибка сохранения", f"Произошла ошибка при сохранении конфигурации: {e}")
                self.payroll_system.logger.log_activity(f"Неизвестная ошибка при сохранении конфигурации: {e}")

        config_buttons_frame = ttk.Frame(config_window, padding="10")
        config_buttons_frame.pack(pady=10)
        ttk.Button(config_buttons_frame, text="Сохранить и Закрыть", command=save_config_and_close).pack(side=tk.LEFT,
                                                                                                         padx=5)
        ttk.Button(config_buttons_frame, text="Отмена", command=config_window.destroy).pack(side=tk.LEFT, padx=5)

        config_window.protocol("WM_DELETE_WINDOW", config_window.destroy)
        config_window.focus_set()

    def _on_employee_select(self, event):
        """Загружает данные выбранного сотрудника в поля ввода."""
        selected_item = self.employee_tree.selection()
        if selected_item:
            employee_id = self.employee_tree.item(selected_item, "values")[0]
            employee = self.payroll_system.get_employee(employee_id)
            if employee:
                self.employee_id_entry.config(state='normal')
                self.employee_id_entry.delete(0, tk.END)
                self.employee_id_entry.insert(0, employee.employee_id)
                self.employee_id_entry.config(state='readonly')

                self.employee_name_entry.delete(0, tk.END)
                self.employee_name_entry.insert(0, employee.name)

                self.base_salary_type_var.set(employee.base_salary_type)
                self.base_salary_value_entry.delete(0, tk.END)
                self.base_salary_value_entry.insert(0, str(employee.base_salary_value))

                self.tax_exemptions_entry.delete(0, tk.END)
                self.tax_exemptions_entry.insert(0, str(employee.tax_exemptions))

                self.hours_worked_entry.delete(0, tk.END)
                self.days_worked_entry.delete(0, tk.END)

                if employee.base_salary_type == 'hourly':
                    self.hours_worked_entry.insert(0,
                                                   str(employee.hours_worked if employee.hours_worked is not None else ""))
                elif employee.base_salary_type == 'daily':
                    self.days_worked_entry.insert(0,
                                                  str(employee.days_worked if employee.days_worked is not None else ""))
                self._update_salary_type_fields()

    def _filter_employees_gui(self, event=None):
        """Фильтрует список сотрудников в Treeview на основе ввода поиска и выбранного типа."""
        search_query = self.search_entry.get().strip().lower()
        filter_type = self.filter_salary_type_var.get()

        for item in self.employee_tree.get_children():
            self.employee_tree.delete(item)

        for emp_id, emp in self.payroll_system.employees.items():
            match_search = (search_query in emp.employee_id.lower() or
                            search_query in emp.name.lower() or
                            not search_query)

            match_filter = (filter_type == "Все" or
                            emp.base_salary_type == filter_type)

            if match_search and match_filter:
                self.employee_tree.insert("", "end", iid=emp_id,
                                          values=(emp.employee_id, emp.name, emp.base_salary_type,
                                                  f"{emp.base_salary_value:.2f}"))

    def _populate_employee_list(self):
        """Заполняет Treeview списком сотрудников."""
        self._filter_employees_gui()

    def _clear_input_fields(self):
        """Очищает поля ввода после добавления/обновления."""
        self.employee_id_entry.config(state='normal')
        self.employee_id_entry.delete(0, tk.END)
        self.employee_id_entry.insert(0, "EMP001")
        self.employee_id_entry.config(state='readonly')

        self.employee_name_entry.delete(0, tk.END)
        self.employee_name_entry.insert(0, "Иван Иванов")

        self.base_salary_type_var.set("monthly")
        self.base_salary_value_entry.delete(0, tk.END)
        self.base_salary_value_entry.insert(0, "4500.0")

        self.hours_worked_entry.delete(0, tk.END)
        self.hours_worked_entry.insert(0, "160")
        self.days_worked_entry.delete(0, tk.END)
        self.days_worked_entry.insert(0, "20")
        self._update_salary_type_fields()

        self.tax_exemptions_entry.delete(0, tk.END)
        self.tax_exemptions_entry.insert(0, "100.0")

    def _calculate_all_payroll_gui(self):
        """Обработчик кнопки для расчета зарплаты всех сотрудников."""
        self.payroll_summary_text.delete(1.0, tk.END)
        all_results = self.payroll_system.process_all_payroll()

        if not all_results:
            self.payroll_summary_text.insert(tk.END, "Нет результатов для отображения.")
            return

        for emp_id, result in all_results.items():
            employee = self.payroll_system.get_employee(emp_id)
            employee_display_name = employee.name if employee else emp_id
            self.payroll_summary_text.insert(tk.END,
                                             f"--- Результаты для сотрудника: {employee_display_name} (ID: {emp_id}) ---\n")
            self.payroll_summary_text.insert(tk.END, result.get_summary() + "\n\n")

        messagebox.showinfo("Расчет завершен", "Расчет заработной платы для всех сотрудников завершен.")

    def _export_payroll_results_csv(self):
        """Экспортирует результаты расчета заработной платы в CSV файл."""
        all_results = self.payroll_system.process_all_payroll()
        if not all_results:
            messagebox.showwarning("Предупреждение", "Нет данных для экспорта.")
            return

        try:
            file_path = simpledialog.askstring("Экспорт в CSV", "Введите имя файла (например, payroll_results.csv):")
            if not file_path:
                return

            if not file_path.endswith(".csv"):
                file_path += ".csv"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(
                    "ID сотрудника,Имя сотрудника,Валовая заработная плата,Чистая заработная плата,Подоходный налог,"
                    "Соц. страхование (сотрудник),Другие вычеты,Соц. страхование (работодатель)\n")

                for emp_id, result in all_results.items():
                    employee = self.payroll_system.get_employee(emp_id)
                    employee_name = employee.name if employee else "N/A"
                    income_tax = result.taxes_breakdown.get("Подоходный налог", 0)
                    employee_social_security = result.taxes_breakdown.get("Социальное страхование (сотрудник)", 0)
                    other_deductions_total = sum(result.deductions_breakdown.values())
                    employer_social_security = result.employer_contributions_breakdown.get(
                        "Социальное страхование (работодатель)", 0)

                    f.write(f"{emp_id},"
                            f"\"{employee_name}\","
                            f"{result.gross_pay:.2f},"
                            f"{result.net_pay:.2f},"
                            f"{income_tax:.2f},"
                            f"{employee_social_security:.2f},"
                            f"{other_deductions_total:.2f},"
                            f"{employer_social_security:.2f}\n")
            messagebox.showinfo("Экспорт завершен", f"Результаты успешно экспортированы в '{file_path}'.")
            self.payroll_system.logger.log_activity(f"Результаты расчета экспортированы в CSV: '{file_path}'.")
        except Exception as e:
            messagebox.showerror("Ошибка экспорта", f"Произошла ошибка при экспорте: {e}")
            self.payroll_system.logger.log_activity(f"Ошибка экспорта результатов расчета в CSV: {e}")


if __name__ == "__main__":
    app = PayrollApp()
    app.mainloop()
