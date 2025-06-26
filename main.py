import yaml
import json
from pathlib import Path
import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QLineEdit, QComboBox, QPushButton,
    QTextEdit, QTreeWidget, QTreeWidgetItem, QTabWidget,
    QMessageBox, QInputDialog, QLabel, QHeaderView, QSizePolicy,
    QDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QGuiApplication, QColor, QPalette

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
    def __init__(self, config_path="config.yaml"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except yaml.YAMLError as e:
                QMessageBox.critical(None, "Ошибка конфигурации",
                                     f"Ошибка при анализе файла конфигурации YAML: {e}\nИспользование конфигурации по умолчанию.")
                return yaml.safe_load(DEFAULT_CONFIG)
        else:
            QMessageBox.information(None, "Информация",
                                    f"Файл конфигурации '{self.config_path}' не найден. Использование конфигурации по умолчанию.")
            return yaml.safe_load(DEFAULT_CONFIG)

    def get_tax_brackets(self):
        return self.config.get('tax_brackets', [])

    def get_social_security_config(self):
        return self.config.get('social_security', {})

    def get_default_deductions(self):
        return self.config.get('deductions', {})

    def save_config(self):
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(self.config, f, indent=2, allow_unicode=True)
            QMessageBox.information(None, "Сохранение конфигурации", "Конфигурация успешно сохранена.")
        except IOError as e:
            QMessageBox.critical(None, "Ошибка сохранения", f"Ошибка сохранения файла конфигурации: {e}")


class PayrollResult:
    def __init__(self, gross_pay, net_pay, taxes_breakdown, deductions_breakdown, employer_contributions_breakdown):
        self.gross_pay = gross_pay
        self.net_pay = net_pay
        self.taxes_breakdown = taxes_breakdown
        self.deductions_breakdown = deductions_breakdown
        self.employer_contributions_breakdown = employer_contributions_breakdown

    def get_summary(self):
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
    def __init__(self, config_path="config.yaml"):
        self.config_loader = ConfigLoader(config_path)
        self.tax_brackets = sorted(self.config_loader.get_tax_brackets(), key=lambda x: x.get('min_income', 0))
        self.social_security_config = self.config_loader.get_social_security_config()
        self.default_deductions_config = self.config_loader.get_default_deductions()

    def _calculate_income_tax(self, gross_income, tax_exemptions):
        taxable_income = max(0.0, gross_income - tax_exemptions)
        total_income_tax = 0.0

        previous_tier_max_income = 0.0

        for bracket in self.tax_brackets:
            min_threshold = bracket.get('min_income', 0.0)
            max_threshold = bracket.get('max_income')
            rate = bracket.get('rate', 0.0)

            if taxable_income <= min_threshold and min_threshold != 0.0:
                break

            current_tier_upper_bound = min(taxable_income, max_threshold if max_threshold is not None else float('inf'))

            current_tier_lower_bound = max(min_threshold, previous_tier_max_income)

            taxable_amount_in_current_tier = max(0.0, current_tier_upper_bound - current_tier_lower_bound)

            total_income_tax += taxable_amount_in_current_tier * rate

            previous_tier_max_income = max(previous_tier_max_income,
                                           max_threshold if max_threshold is not None else taxable_income)
        return total_income_tax

    def _calculate_employee_social_security_tax(self, gross_income):
        employee_rate = self.social_security_config.get('employee_rate', 0.0)
        max_contribution = self.social_security_config.get('max_employee_contribution', float('inf'))

        contribution = gross_income * employee_rate
        return min(contribution, max_contribution)

    def _calculate_employer_social_security_contribution(self, gross_income):
        employer_rate = self.social_security_config.get('employer_rate', 0.0)
        max_contribution = self.social_security_config.get('max_employer_contribution', float('inf'))

        contribution = gross_income * employer_rate
        return min(contribution, max_contribution)

    def _calculate_other_deductions(self, gross_income, custom_deductions):
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
    def __init__(self, log_file="activity_log.txt"):
        self.log_file = Path(log_file)
        self._ensure_log_file_exists()

    def _ensure_log_file_exists(self):
        if not self.log_file.exists():
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write(f"--- Журнал активности системы расчета заработной платы - {datetime.datetime.now()} ---\n")
            except IOError as e:
                print(f"Ошибка при создании файла журнала: {e}")

    def log_activity(self, activity_description):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {activity_description}\n"
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_entry)
        except IOError as e:
            print(f"Ошибка при записи в файл журнала: {e}")

    def get_log_content(self):
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "Журнал активности пуст или не найден."
        except IOError as e:
            return f"Ошибка при чтении файла журнала: {e}"


class PayrollSystem:
    def __init__(self, config_path="config.yaml", employees_data_file="employees.json", log_file="activity_log.txt"):
        self.employees = {}
        self.config_loader = ConfigLoader(config_path)
        self.calculator = PayrollCalculator(config_path)
        self.employees_data_file = Path(employees_data_file)
        self.logger = ActivityLogger(log_file)
        self._load_employees()

    def add_employee(self, employee: Employee):
        action = "обновлен" if employee.employee_id in self.employees else "добавлен"
        self.employees[employee.employee_id] = employee
        self._save_employees()
        self.logger.log_activity(f"Сотрудник {employee.name} (ID: {employee.employee_id}) успешно {action}.")

    def delete_employee(self, employee_id):
        if employee_id in self.employees:
            employee_name = self.employees[employee_id].name
            del self.employees[employee_id]
            self._save_employees()
            self.logger.log_activity(f"Сотрудник {employee_name} (ID: {employee_id}) успешно удален.")
            QMessageBox.information(None, "Успех", f"Сотрудник {employee_id} успешно удален.")
            return True
        else:
            QMessageBox.critical(None, "Ошибка", f"Сотрудник с ID {employee_id} не найден.")
            return False

    def get_employee(self, employee_id):
        return self.employees.get(employee_id)

    def process_all_payroll(self):
        all_payroll_results = {}
        if not self.employees:
            self.logger.log_activity("Попытка расчета заработной платы: нет сотрудников в системе.")
            QMessageBox.information(None, "Информация", "Нет сотрудников для расчета заработной платы.")
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
                QMessageBox.critical(None, "Ошибка расчета", f"Ошибка при расчете для сотрудника {employee_id}: {e}")
            except Exception as e:
                self.logger.log_activity(
                    f"Неизвестная ошибка при расчете для сотрудника {employee.name} (ID: {employee_id}): {e}")
                QMessageBox.critical(None, "Неизвестная ошибка",
                                     f"Неизвестная ошибка при расчете для сотрудника {employee_id}: {e}")
        self.logger.log_activity("Расчет заработной платы для всех сотрудников завершен.")
        return all_payroll_results

    def _save_employees(self):
        try:
            with open(self.employees_data_file, 'w', encoding='utf-8') as f:
                json.dump([emp.to_dict() for emp in self.employees.values()], f, indent=4, ensure_ascii=False)
        except IOError as e:
            self.logger.log_activity(f"Ошибка сохранения данных сотрудников: {e}")
            QMessageBox.critical(None, "Ошибка сохранения", f"Ошибка сохранения данных сотрудников: {e}")

    def _load_employees(self):
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
                QMessageBox.critical(None, "Ошибка загрузки",
                                     f"Ошибка чтения файла данных сотрудников JSON: {e}\nНачинаем с пустого списка сотрудников.")
            except IOError as e:
                self.logger.log_activity(
                    f"Ошибка загрузки данных сотрудников: {e}. Начинаем с пустого списка сотрудников.")
                QMessageBox.critical(None, "Ошибка загрузки",
                                     f"Ошибка загрузки данных сотрудников: {e}\nНачинаем с пустого списка сотрудников.")
        else:
            self.logger.log_activity(
                f"Файл данных сотрудников '{self.employees_data_file}' не найден. Начинаем с пустого списка сотрудников.")
            QMessageBox.information(None, "Информация",
                                    f"Файл данных сотрудников '{self.employees_data_file}' не найден. Начинаем с пустого списка сотрудников.")

    def clear_all_data(self):
        self.employees = {}

        if self.employees_data_file.exists():
            try:
                self.employees_data_file.unlink()
                self.logger.log_activity(f"Файл данных сотрудников '{self.employees_data_file}' удален.")
            except Exception as e:
                self.logger.log_activity(
                    f"Ошибка при удалении файла данных сотрудников '{self.employees_data_file}': {e}")

        if self.config_loader.config_path.exists():
            try:
                self.config_loader.config_path.unlink()
                self.logger.log_activity(f"Файл конфигурации '{self.config_loader.config_path}' удален.")
            except Exception as e:
                self.logger.log_activity(
                    f"Ошибка при удалении файла конфигурации '{self.config_loader.config_path}': {e}")

        try:
            with open(self.config_loader.config_path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_CONFIG)
            self.config_loader = ConfigLoader(self.config_loader.config_path)
            self.calculator = PayrollCalculator(self.config_loader.config_path)
            self.logger.log_activity(f"Файл конфигурации по умолчанию создан заново: {self.config_loader.config_path}")
        except Exception as e:
            self.logger.log_activity(f"Ошибка при создании файла конфигурации по умолчанию: {e}")

        if self.logger.log_file.exists():
            try:
                with open(self.logger.log_file, 'w', encoding='utf-8') as f:
                    f.write(
                        f"--- Журнал активности системы расчета заработной платы - {datetime.datetime.now()} (Данные очищены) ---\n")
                self.logger.log_activity("Журнал активности очищен.")
            except Exception as e:
                print(f"Ошибка при очистке файла журнала: {e}")


class CustomDialog(QInputDialog):
    def __init__(self, parent=None, title="", label="", initialValue="", okButtonText="ОК", cancelButtonText="Отмена"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setLabelText(label)
        self.setTextValue(initialValue)
        self.setOkButtonText(okButtonText)
        self.setCancelButtonText(cancelButtonText)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

    @staticmethod
    def get_string(parent=None, title="", label="", initialValue="", okButtonText="ОК", cancelButtonText="Отмена"):
        dialog = CustomDialog(parent, title, label, initialValue, okButtonText, cancelButtonText)
        ok = dialog.exec()
        if ok:
            return dialog.textValue()
        return None

    @staticmethod
    def get_float(parent=None, title="", label="", initialValue=0.0, okButtonText="ОК", cancelButtonText="Отмена"):
        dialog = CustomDialog(parent, title, label, str(initialValue), okButtonText, cancelButtonText)
        dialog.setInputMode(QInputDialog.InputMode.DoubleInput)
        ok = dialog.exec()
        if ok:
            try:
                return float(dialog.textValue())
            except ValueError:
                return None
        return None

    @staticmethod
    def get_int(parent=None, title="", label="", initialValue=0, okButtonText="ОК", cancelButtonText="Отмена"):
        dialog = CustomDialog(parent, title, label, str(initialValue), okButtonText, cancelButtonText)
        dialog.setInputMode(QInputDialog.InputMode.IntInput)
        ok = dialog.exec()
        if ok:
            try:
                return int(dialog.textValue())
            except ValueError:
                return None
        return None

    @staticmethod
    def get_choice(parent=None, title="", label="", items=[], initialItem="", editable=False, okButtonText="ОК",
                   cancelButtonText="Отмена"):
        dialog = QInputDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setLabelText(label)
        dialog.setComboBoxItems(items)
        dialog.setOkButtonText(okButtonText)
        dialog.setCancelButtonText(cancelButtonText)
        dialog.setComboBoxEditable(editable)
        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        if initialItem in items:
            dialog.setTextValue(initialItem)

        ok = dialog.exec()
        if ok:
            return dialog.textValue()
        return None


class EmployeeDetailsWindow(QDialog):
    employee_updated = pyqtSignal()

    def __init__(self, employee: Employee, payroll_system: PayrollSystem, parent=None):
        super().__init__(parent)
        self.employee = employee
        self.payroll_system = payroll_system
        self.setWindowTitle(f"Детали сотрудника: {employee.employee_id} ({employee.name})")
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        employee_data_group = QGroupBox("Редактирование данных сотрудника")
        employee_data_layout = QFormLayout(employee_data_group)

        self.id_entry = QLineEdit(self.employee.employee_id)
        self.id_entry.setReadOnly(True)
        employee_data_layout.addRow("ID сотрудника:", self.id_entry)

        self.name_entry = QLineEdit(self.employee.name)
        employee_data_layout.addRow("Имя сотрудника:", self.name_entry)

        self.base_salary_type_combo = QComboBox()
        self.base_salary_type_combo.addItems(['monthly', 'hourly', 'daily'])
        self.base_salary_type_combo.setCurrentText(self.employee.base_salary_type)
        employee_data_layout.addRow("Тип ЗП:", self.base_salary_type_combo)

        self.base_salary_value_entry = QLineEdit(str(self.employee.base_salary_value))
        employee_data_layout.addRow("Значение ЗП:", self.base_salary_value_entry)

        self.hours_worked_entry = QLineEdit(
            str(self.employee.hours_worked if self.employee.hours_worked is not None else ""))
        employee_data_layout.addRow("Отработано часов:", self.hours_worked_entry)

        self.days_worked_entry = QLineEdit(
            str(self.employee.days_worked if self.employee.days_worked is not None else ""))
        employee_data_layout.addRow("Отработано дней:", self.days_worked_entry)

        self.tax_exemptions_entry = QLineEdit(str(self.employee.tax_exemptions))
        employee_data_layout.addRow("Налоговые льготы:", self.tax_exemptions_entry)

        main_layout.addWidget(employee_data_group)

        bonuses_group = QGroupBox("Бонусы")
        bonuses_layout = QVBoxLayout(bonuses_group)
        self.bonuses_tree = QTreeWidget()
        self.bonuses_tree.setHeaderLabels(["Название", "Тип", "Значение"])
        self.bonuses_tree.setColumnCount(3)
        self.bonuses_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._populate_bonuses_tree()
        bonuses_layout.addWidget(self.bonuses_tree)

        bonus_buttons_layout = QHBoxLayout()
        add_bonus_button = QPushButton("Добавить бонус")
        add_bonus_button.clicked.connect(self._add_bonus)
        remove_bonus_button = QPushButton("Удалить бонус")
        remove_bonus_button.clicked.connect(self._remove_bonus)
        bonus_buttons_layout.addWidget(add_bonus_button)
        bonus_buttons_layout.addWidget(remove_bonus_button)
        bonuses_layout.addLayout(bonus_buttons_layout)
        main_layout.addWidget(bonuses_group)

        deductions_group = QGroupBox("Пользовательские вычеты")
        deductions_layout = QVBoxLayout(deductions_group)
        self.deductions_tree = QTreeWidget()
        self.deductions_tree.setHeaderLabels(["Название", "Тип", "Значение"])
        self.deductions_tree.setColumnCount(3)
        self.deductions_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._populate_deductions_tree()
        deductions_layout.addWidget(self.deductions_tree)

        deduction_buttons_layout = QHBoxLayout()
        add_deduction_button = QPushButton("Добавить вычет")
        add_deduction_button.clicked.connect(self._add_deduction)
        remove_deduction_button = QPushButton("Удалить вычет")
        remove_deduction_button.clicked.connect(self._remove_deduction)
        deduction_buttons_layout.addWidget(add_deduction_button)
        deduction_buttons_layout.addWidget(remove_deduction_button)
        deductions_layout.addLayout(deduction_buttons_layout)
        main_layout.addWidget(deductions_group)

        save_cancel_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.clicked.connect(self._save_and_close)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        save_cancel_layout.addWidget(save_button)
        save_cancel_layout.addWidget(cancel_button)
        main_layout.addLayout(save_cancel_layout)

    def _populate_bonuses_tree(self):
        self.bonuses_tree.clear()
        for bonus in self.employee.bonuses:
            item = QTreeWidgetItem([
                bonus.get('name', ''),
                bonus.get('type', ''),
                str(bonus.get('value', ''))
            ])
            self.bonuses_tree.addTopLevelItem(item)

    def _add_bonus(self):
        name, ok = QInputDialog.getText(self, "Добавить бонус", "Название бонуса:")
        if ok and name:
            bonus_type, ok = QInputDialog.getItem(self, "Добавить бонус", "Тип (amount/percentage):",
                                                  ['amount', 'percentage'], 0, False)
            if ok and bonus_type:
                value, ok = QInputDialog.getDouble(self, "Добавить бонус", "Значение:")
                if ok:
                    if bonus_type == 'percentage' and not (0 <= value <= 1):
                        QMessageBox.critical(self, "Ошибка", "Процент бонуса должен быть между 0 и 1.")
                        return
                    self.employee.bonuses.append({'name': name, 'type': bonus_type, 'value': value})
                    self._populate_bonuses_tree()
                else:
                    QMessageBox.information(self, "Отмена", "Добавление бонуса отменено.")
            else:
                QMessageBox.information(self, "Отмена", "Добавление бонуса отменено.")
        else:
            QMessageBox.information(self, "Отмена", "Добавление бонуса отменено.")

    def _remove_bonus(self):
        selected_items = self.bonuses_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите бонус для удаления.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления", "Вы уверены, что хотите удалить выбранные бонусы?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                name_to_remove = item.text(0)
                type_to_remove = item.text(1)
                value_to_remove = float(item.text(2))
                self.employee.bonuses = [b for b in self.employee.bonuses if not (b.get('name') == name_to_remove and
                                                                                  b.get('type') == type_to_remove and
                                                                                  b.get('value') == value_to_remove)]
            self._populate_bonuses_tree()
            QMessageBox.information(self, "Успех", "Выбранные бонусы удалены.")

    def _populate_deductions_tree(self):
        self.deductions_tree.clear()
        for ded in self.employee.custom_deductions:
            item = QTreeWidgetItem([
                ded.get('name', ''),
                ded.get('type', ''),
                str(ded.get('value', ''))
            ])
            self.deductions_tree.addTopLevelItem(item)

    def _add_deduction(self):
        name, ok = QInputDialog.getText(self, "Добавить вычет", "Название вычета:")
        if ok and name:
            deduction_type, ok = QInputDialog.getItem(self, "Добавить вычет", "Тип (fixed/percentage):",
                                                      ['fixed', 'percentage'], 0, False)
            if ok and deduction_type:
                value, ok = QInputDialog.getDouble(self, "Добавить вычет", "Значение:")
                if ok:
                    if deduction_type == 'percentage' and not (0 <= value <= 1):
                        QMessageBox.critical(self, "Ошибка", "Процент вычета должен быть между 0 и 1.")
                        return
                    self.employee.custom_deductions.append({'name': name, 'type': deduction_type, 'value': value})
                    self._populate_deductions_tree()
                else:
                    QMessageBox.information(self, "Отмена", "Добавление вычета отменено.")
            else:
                QMessageBox.information(self, "Отмена", "Добавление вычета отменено.")
        else:
            QMessageBox.information(self, "Отмена", "Добавление вычета отменено.")

    def _remove_deduction(self):
        selected_items = self.deductions_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Выберите вычет для удаления.")
            return

        reply = QMessageBox.question(self, "Подтверждение удаления", "Вы уверены, что хотите удалить выбранные вычеты?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                name_to_remove = item.text(0)
                type_to_remove = item.text(1)
                value_to_remove = float(item.text(2))
                self.employee.custom_deductions = [d for d in self.employee.custom_deductions if
                                                   not (d.get('name') == name_to_remove and
                                                        d.get('type') == type_to_remove and
                                                        d.get('value') == value_to_remove)]
            self._populate_deductions_tree()
            QMessageBox.information(self, "Успех", "Выбранные вычеты удалены.")

    def _save_and_close(self):
        try:
            self.employee.name = self.name_entry.text().strip()
            if not self.employee.name:
                raise ValueError("Имя сотрудника не может быть пустым.")

            self.employee.base_salary_type = self.base_salary_type_combo.currentText()
            self.employee.base_salary_value = float(self.base_salary_value_entry.text())
            if self.employee.base_salary_value < 0:
                raise ValueError("Базовая зарплата не может быть отрицательной.")

            hours_worked_str = self.hours_worked_entry.text().strip()
            self.employee.hours_worked = int(hours_worked_str) if hours_worked_str else None
            if self.employee.hours_worked is not None and self.employee.hours_worked < 0:
                raise ValueError("Отработано часов не может быть отрицательным.")

            days_worked_str = self.days_worked_entry.text().strip()
            self.employee.days_worked = int(days_worked_str) if days_worked_str else None
            if self.employee.days_worked is not None and self.employee.days_worked < 0:
                raise ValueError("Отработано дней не может быть отрицательным.")

            self.employee.tax_exemptions = float(self.tax_exemptions_entry.text())
            if self.employee.tax_exemptions < 0:
                raise ValueError("Налоговые льготы не могут быть отрицательными.")

            self.payroll_system.add_employee(self.employee)
            QMessageBox.information(self, "Успех",
                                    f"Данные сотрудника {self.employee.employee_id} ({self.employee.name}) успешно обновлены.")
            self.employee_updated.emit()
            self.accept()

        except ValueError as e:
            QMessageBox.critical(self, "Ошибка сохранения", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Неизвестная ошибка", f"Ошибка при сохранении: {e}")


class ConfigEditorWindow(QDialog):
    config_updated = pyqtSignal()

    def __init__(self, payroll_system: PayrollSystem, parent=None):
        super().__init__(parent)
        self.payroll_system = payroll_system
        self.setWindowTitle("Редактирование конфигурации")
        self.setModal(True)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        notebook = QTabWidget()
        main_layout.addWidget(notebook)

        tax_brackets_tab = QWidget()
        notebook.addTab(tax_brackets_tab, "Налоговые скобки")
        tax_layout = QVBoxLayout(tax_brackets_tab)

        self.tax_tree = QTreeWidget()
        self.tax_tree.setHeaderLabels(["Мин. доход", "Макс. доход", "Ставка (%)"])
        self.tax_tree.setColumnCount(3)
        self.tax_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        tax_layout.addWidget(self.tax_tree)
        self._populate_tax_tree()

        tax_buttons_layout = QHBoxLayout()
        add_tax_button = QPushButton("Добавить")
        add_tax_button.clicked.connect(self._add_tax_bracket)
        remove_tax_button = QPushButton("Удалить")
        remove_tax_button.clicked.connect(self._remove_tax_bracket)
        tax_buttons_layout.addWidget(add_tax_button)
        tax_buttons_layout.addWidget(remove_tax_button)
        tax_layout.addLayout(tax_buttons_layout)

        social_security_tab = QWidget()
        notebook.addTab(social_security_tab, "Социальное страхование")
        ss_layout = QFormLayout(social_security_tab)

        ss_config = self.payroll_system.config_loader.get_social_security_config()

        self.employee_rate_entry = QLineEdit(str(ss_config.get('employee_rate', 0.0) * 100))
        ss_layout.addRow("Ставка сотрудника (%):", self.employee_rate_entry)

        self.max_employee_contrib_entry = QLineEdit(str(ss_config.get('max_employee_contribution', 0.0)))
        ss_layout.addRow("Макс. взнос сотрудника:", self.max_employee_contrib_entry)

        self.employer_rate_entry = QLineEdit(str(ss_config.get('employer_rate', 0.0) * 100))
        ss_layout.addRow("Ставка работодателя (%):", self.employer_rate_entry)

        self.max_employer_contrib_entry = QLineEdit(str(ss_config.get('max_employer_contribution', 0.0)))
        ss_layout.addRow("Макс. взнос работодателя:", self.max_employer_contrib_entry)

        default_deductions_tab = QWidget()
        notebook.addTab(default_deductions_tab, "Вычеты по умолчанию")
        ded_layout = QVBoxLayout(default_deductions_tab)

        self.deductions_tree_config = QTreeWidget()
        self.deductions_tree_config.setHeaderLabels(["Название", "Тип", "Значение"])
        self.deductions_tree_config.setColumnCount(3)
        self.deductions_tree_config.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        ded_layout.addWidget(self.deductions_tree_config)
        self._populate_deductions_tree()

        ded_buttons_layout = QHBoxLayout()
        add_ded_button = QPushButton("Добавить")
        add_ded_button.clicked.connect(self._add_default_deduction)
        remove_ded_button = QPushButton("Удалить")
        remove_ded_button.clicked.connect(self._remove_default_deduction)
        ded_buttons_layout.addWidget(add_ded_button)
        ded_buttons_layout.addWidget(remove_ded_button)
        ded_layout.addLayout(ded_buttons_layout)

        save_cancel_layout = QHBoxLayout()
        save_button = QPushButton("Сохранить и Закрыть")
        save_button.clicked.connect(self._save_config_and_close)
        cancel_button = QPushButton("Отмена")
        cancel_button.clicked.connect(self.reject)
        save_cancel_layout.addWidget(save_button)
        save_cancel_layout.addWidget(cancel_button)
        main_layout.addLayout(save_cancel_layout)

    def _populate_tax_tree(self):
        self.tax_tree.clear()
        sorted_brackets = sorted(self.payroll_system.config_loader.get_tax_brackets(),
                                 key=lambda x: x.get('min_income', 0))
        for bracket in sorted_brackets:
            max_income = str(bracket.get('max_income', '')) if bracket.get('max_income') is not None else ""
            item = QTreeWidgetItem([
                f"{bracket.get('min_income'):.2f}",
                max_income,
                f"{bracket.get('rate') * 100:.2f}"
            ])
            self.tax_tree.addTopLevelItem(item)

    def _add_tax_bracket(self):
        min_income, ok_min = QInputDialog.getDouble(self, "Добавить скобку", "Минимальный доход:")
        if not ok_min: return

        max_income_str, ok_max = QInputDialog.getText(self, "Добавить скобку",
                                                      "Максимальный доход (оставьте пустым для безлимита):")
        max_income = float(max_income_str) if ok_max and max_income_str else None

        rate, ok_rate = QInputDialog.getDouble(self, "Добавить скобку", "Ставка (например, 0.10 для 10%):", decimals=3)
        if not ok_rate: return

        if not (0 <= rate <= 1):
            QMessageBox.critical(self, "Ошибка", "Ставка должна быть от 0 до 1.")
            return

        new_bracket = {'min_income': min_income, 'rate': rate}
        if max_income is not None:
            new_bracket['max_income'] = max_income

        self.payroll_system.config_loader.config['tax_brackets'].append(new_bracket)
        self.payroll_system.config_loader.config['tax_brackets'] = sorted(
            self.payroll_system.config_loader.config['tax_brackets'],
            key=lambda x: x.get('min_income', 0)
        )
        self._populate_tax_tree()
        self.payroll_system.logger.log_activity(
            f"Добавлена налоговая скобка: Мин. {min_income}, Макс. {max_income}, Ставка {rate * 100:.2f}%.")

    def _remove_tax_bracket(self):
        selected_item = self.tax_tree.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Предупреждение", "Выберите налоговую скобку для удаления.")
            return

        values = [selected_item.text(i) for i in range(selected_item.columnCount())]
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
            self._populate_tax_tree()
            QMessageBox.information(self, "Успех", "Налоговая скобка удалена.")
            self.payroll_system.logger.log_activity(
                f"Удалена налоговая скобка: Мин. {min_inc}, Макс. {max_inc}, Ставка {rate_val * 100:.2f}%.")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось найти и удалить налоговую скобку.")

    def _populate_deductions_tree(self):
        self.deductions_tree_config.clear()
        for ded_name, ded_info in self.payroll_system.config_loader.get_default_deductions().items():
            value_display = f"{ded_info.get('amount', 0):.2f}" if ded_info.get(
                'type') == 'fixed' else f"{ded_info.get('rate', 0) * 100:.2f}%"
            item = QTreeWidgetItem([ded_name, ded_info.get('type', ''), value_display])
            self.deductions_tree_config.addTopLevelItem(item)

    def _add_default_deduction(self):
        name, ok_name = QInputDialog.getText(self, "Добавить вычет по умолчанию", "Название вычета:")
        if not ok_name or not name: return

        deduction_type, ok_type = QInputDialog.getItem(self, "Добавить вычет по умолчанию", "Тип (fixed/percentage):",
                                                       ['fixed', 'percentage'], 0, False)
        if not ok_type or not deduction_type: return

        value, ok_value = QInputDialog.getDouble(self, "Добавить вычет по умолчанию", "Значение (для % от 0 до 1):")
        if not ok_value: return

        if deduction_type == 'percentage' and not (0 <= value <= 1):
            QMessageBox.critical(self, "Ошибка", "Процент вычета должен быть между 0 и 1.")
            return

        if name in self.payroll_system.config_loader.config['deductions']:
            QMessageBox.warning(self, "Предупреждение", f"Вычет '{name}' уже существует и будет обновлен.")

        if deduction_type == 'fixed':
            self.payroll_system.config_loader.config['deductions'][name] = {'type': deduction_type, 'amount': value}
        else:
            self.payroll_system.config_loader.config['deductions'][name] = {'type': deduction_type, 'rate': value}
        self._populate_deductions_tree()
        self.payroll_system.logger.log_activity(f"Добавлен/обновлен вычет по умолчанию '{name}'.")

    def _remove_default_deduction(self):
        selected_item = self.deductions_tree_config.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "Предупреждение", "Выберите вычет для удаления.")
            return

        name_to_remove = selected_item.text(0)
        if name_to_remove in self.payroll_system.config_loader.config['deductions']:
            del self.payroll_system.config_loader.config['deductions'][name_to_remove]
            self._populate_deductions_tree()
            QMessageBox.information(self, "Успех", f"Вычет '{name_to_remove}' удален.")
            self.payroll_system.logger.log_activity(f"Удален вычет по умолчанию '{name_to_remove}'.")
        else:
            QMessageBox.critical(self, "Ошибка", "Не удалось найти и удалить вычет.")

    def _save_config_and_close(self):
        try:
            self.payroll_system.config_loader.config['social_security']['employee_rate'] = float(
                self.employee_rate_entry.text()) / 100
            self.payroll_system.config_loader.config['social_security']['max_employee_contribution'] = float(
                self.max_employee_contrib_entry.text())
            self.payroll_system.config_loader.config['social_security']['employer_rate'] = float(
                self.employer_rate_entry.text()) / 100
            self.payroll_system.config_loader.config['social_security']['max_employer_contribution'] = float(
                self.max_employer_contrib_entry.text())

            if not (0 <= self.payroll_system.config_loader.config['social_security']['employee_rate'] <= 1 and
                    0 <= self.payroll_system.config_loader.config['social_security']['employer_rate'] <= 1):
                raise ValueError("Ставки социального страхования должны быть от 0 до 1 (0% до 100%).")

            self.payroll_system.config_loader.save_config()
            self.payroll_system.calculator = PayrollCalculator(self.payroll_system.config_loader.config_path)
            self.payroll_system.logger.log_activity("Конфигурация системы успешно обновлена.")
            self.config_updated.emit()
            self.accept()
        except ValueError as e:
            QMessageBox.critical(self, "Ошибка ввода", str(e))
            self.payroll_system.logger.log_activity(f"Ошибка ввода при обновлении конфигурации: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", f"Произошла ошибка при сохранении конфигурации: {e}")
            self.payroll_system.logger.log_activity(f"Неизвестная ошибка при сохранении конфигурации: {e}")


class PayrollApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система расчета заработной платы")
        self.resize(1200, 800)

        font = QFont("Arial", 10)
        QApplication.setFont(font)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #3c3c3c;
                color: #f0f0f0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
                background-color: #4a4a4a;
                border-radius: 5px;
                color: #f0f0f0;
            }
            QPushButton {
                background-color: #5cb85c;
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #4cae4c;
            }
            QPushButton:pressed {
                background-color: #449d44;
            }
            QLineEdit, QComboBox, QTextEdit {
                border: 1px solid #666666;
                border-radius: 5px;
                padding: 5px;
                background-color: #4e4e4e;
                color: #f0f0f0;
            }
            QComboBox::drop-down {
                border-left: 1px solid #666666;
            }
            QComboBox::down-arrow {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAcAAAAECAYAAADg/bVnAAAAG0lEQVQIW2NkYGDwYDAwMGAiJgYGFIAaBgZgAAC0gAP2fW12LwAAAABJRU5ErkJggg==);
            }
            QTreeWidget {
                border: 1px solid #666666;
                border-radius: 5px;
                background-color: #4e4e4e;
                color: #f0f0f0;
                alternate-background-color: #5a5a5a;
            }
            QTreeWidget::item:selected {
                background-color: #007bff;
                color: white;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                border-radius: 8px;
                background-color: #3c3c3c;
            }
            QTabBar::tab {
                background: #4a4a4a;
                color: #f0f0f0;
                border: 1px solid #555555;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                padding: 8px 15px;
            }
            QTabBar::tab:selected {
                background: #3c3c3c;
                border-bottom-color: #3c3c3c;
                font-weight: bold;
            }
            QLabel {
                color: #f0f0f0;
            }
        """)

        config_file_path = Path("config.yaml")
        if not config_file_path.exists():
            with open(config_file_path, 'w', encoding='utf-8') as f:
                f.write(DEFAULT_CONFIG)
            print(f"Создан файл конфигурации по умолчанию: {config_file_path}")

        self.payroll_system = PayrollSystem()
        self._create_widgets()
        self._populate_employee_list()
        self._update_overall_statistics()

    def _create_widgets(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(20)

        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setSpacing(10)
        left_frame.setMinimumWidth(400)
        left_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        employee_input_group = QGroupBox("Данные сотрудника")
        employee_input_layout = QFormLayout(employee_input_group)
        employee_input_layout.setContentsMargins(10, 20, 10, 10)
        employee_input_layout.setSpacing(8)

        self.employee_id_entry = QLineEdit("EMP001")
        self.employee_id_entry.setReadOnly(True)
        employee_input_layout.addRow("ID сотрудника:", self.employee_id_entry)

        self.employee_name_entry = QLineEdit("Иван Иванов")
        employee_input_layout.addRow("Имя сотрудника:", self.employee_name_entry)

        self.base_salary_type_combo = QComboBox()
        self.base_salary_type_combo.addItems(['monthly', 'hourly', 'daily'])
        self.base_salary_type_combo.setCurrentText("monthly")
        self.base_salary_type_combo.currentTextChanged.connect(self._update_salary_type_fields)
        employee_input_layout.addRow("Тип базовой зарплаты:", self.base_salary_type_combo)

        self.base_salary_value_entry = QLineEdit("4500.0")
        employee_input_layout.addRow("Значение базовой зарплаты:", self.base_salary_value_entry)

        self.hours_worked_label = QLabel("Отработано часов:")
        self.hours_worked_entry = QLineEdit("160")
        self.hours_worked_layout = QHBoxLayout()
        self.hours_worked_layout.addWidget(self.hours_worked_label)
        self.hours_worked_layout.addWidget(self.hours_worked_entry)
        employee_input_layout.addRow(self.hours_worked_layout)

        self.days_worked_label = QLabel("Отработано дней:")
        self.days_worked_entry = QLineEdit("20")
        self.days_worked_layout = QHBoxLayout()
        self.days_worked_layout.addWidget(self.days_worked_label)
        self.days_worked_layout.addWidget(self.days_worked_entry)
        employee_input_layout.addRow(self.days_worked_layout)

        self.tax_exemptions_entry = QLineEdit("100.0")
        employee_input_layout.addRow("Налоговые льготы:", self.tax_exemptions_entry)

        left_layout.addWidget(employee_input_group)
        self._update_salary_type_fields()

        employee_buttons_layout = QHBoxLayout()
        add_update_button = QPushButton("Добавить/Обновить сотрудника")
        add_update_button.clicked.connect(self._add_employee_gui)
        delete_button = QPushButton("Удалить сотрудника")
        delete_button.clicked.connect(self._delete_employee_gui)
        edit_selected_button = QPushButton("Редактировать выбранного")
        edit_selected_button.clicked.connect(self._edit_selected_employee)
        employee_buttons_layout.addWidget(add_update_button)
        employee_buttons_layout.addWidget(delete_button)
        employee_buttons_layout.addWidget(edit_selected_button)
        left_layout.addLayout(employee_buttons_layout)

        search_filter_group = QGroupBox("Поиск и Фильтр")
        search_filter_layout = QFormLayout(search_filter_group)
        search_filter_layout.setContentsMargins(10, 20, 10, 10)
        search_filter_layout.setSpacing(8)

        self.search_entry = QLineEdit()
        self.search_entry.setPlaceholderText("Поиск по ID или имени...")
        self.search_entry.textChanged.connect(self._filter_employees_gui)
        search_filter_layout.addRow("Поиск (ID/Имя):", self.search_entry)

        self.filter_salary_type_combo = QComboBox()
        self.filter_salary_type_combo.addItems(['Все', 'monthly', 'hourly', 'daily'])
        self.filter_salary_type_combo.currentTextChanged.connect(self._filter_employees_gui)
        search_filter_layout.addRow("Фильтр по типу ЗП:", self.filter_salary_type_combo)

        left_layout.addWidget(search_filter_group)

        employee_list_group = QGroupBox("Список сотрудников")
        employee_list_layout = QVBoxLayout(employee_list_group)
        employee_list_layout.setContentsMargins(10, 20, 10, 10)

        self.employee_tree = QTreeWidget()
        self.employee_tree.setHeaderLabels(["ID", "Имя", "Тип ЗП", "Значение ЗП"])
        self.employee_tree.setColumnCount(4)
        self.employee_tree.header().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.employee_tree.itemSelectionChanged.connect(self._on_employee_select)
        employee_list_layout.addWidget(self.employee_tree)
        left_layout.addWidget(employee_list_group)

        statistics_group = QGroupBox("Общая статистика")
        statistics_layout = QFormLayout(statistics_group)
        statistics_layout.setContentsMargins(10, 20, 10, 10)
        statistics_layout.setSpacing(8)

        self.total_employees_label = QLabel("Всего сотрудников: 0")
        self.total_gross_pay_label = QLabel("Общая валовая ЗП: 0.00")
        self.total_net_pay_label = QLabel("Общая чистая ЗП: 0.00")
        self.total_tax_deductions_label = QLabel("Общие вычеты (налоги и т.д.): 0.00")

        statistics_layout.addRow(self.total_employees_label)
        statistics_layout.addRow(self.total_gross_pay_label)
        statistics_layout.addRow(self.total_net_pay_label)
        statistics_layout.addRow(self.total_tax_deductions_label)

        left_layout.addWidget(statistics_group)

        clear_all_button = QPushButton("Очистить все данные")
        clear_all_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #b00f04;
            }
        """)
        clear_all_button.clicked.connect(self._clear_all_data_gui)
        left_layout.addWidget(clear_all_button)

        main_layout.addWidget(left_frame)

        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.main_notebook = QTabWidget()
        right_layout.addWidget(self.main_notebook)

        payroll_tab = QWidget()
        self.main_notebook.addTab(payroll_tab, "Расчеты")
        self._create_payroll_tab_content(payroll_tab)

        reports_tab = QWidget()
        self.main_notebook.addTab(reports_tab, "Отчеты")
        self._create_reports_tab_content(reports_tab)

        activity_log_tab = QWidget()
        self.main_notebook.addTab(activity_log_tab, "Журнал Активности")
        self._create_activity_log_tab_content(activity_log_tab)

        main_layout.addWidget(right_frame)

    def _create_payroll_tab_content(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        calc_buttons_layout = QHBoxLayout()
        calculate_all_button = QPushButton("Рассчитать зарплату (все)")
        calculate_all_button.clicked.connect(self._calculate_all_payroll_gui)
        export_csv_button = QPushButton("Экспорт результатов в CSV")
        export_csv_button.clicked.connect(self._export_payroll_results_csv)
        edit_config_button = QPushButton("Редактировать конфигурацию")
        edit_config_button.clicked.connect(self._open_config_editor_window)
        calc_buttons_layout.addWidget(calculate_all_button)
        calc_buttons_layout.addWidget(export_csv_button)
        calc_buttons_layout.addWidget(edit_config_button)
        layout.addLayout(calc_buttons_layout)

        result_group = QGroupBox("Результаты расчета")
        result_layout = QVBoxLayout(result_group)
        result_layout.setContentsMargins(10, 20, 10, 10)
        self.payroll_summary_text = QTextEdit()
        self.payroll_summary_text.setReadOnly(True)
        result_layout.addWidget(self.payroll_summary_text)
        layout.addWidget(result_group)

    def _create_reports_tab_content(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        reports_text_group = QGroupBox("Сводные Отчеты")
        reports_text_layout = QVBoxLayout(reports_text_group)
        reports_text_layout.setContentsMargins(10, 20, 10, 10)
        self.reports_text = QTextEdit()
        self.reports_text.setReadOnly(True)
        reports_text_layout.addWidget(self.reports_text)
        layout.addWidget(reports_text_group)

        reports_buttons_layout = QHBoxLayout()
        generate_report_button = QPushButton("Сгенерировать сводный отчет")
        generate_report_button.clicked.connect(self._generate_summary_report)
        export_report_button = QPushButton("Экспорт отчета в CSV")
        export_report_button.clicked.connect(self._export_summary_report_csv)
        reports_buttons_layout.addWidget(generate_report_button)
        reports_buttons_layout.addWidget(export_report_button)
        layout.addLayout(reports_buttons_layout)

    def _create_activity_log_tab_content(self, parent_widget):
        layout = QVBoxLayout(parent_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        log_group = QGroupBox("Системный Журнал Активности")
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(10, 20, 10, 10)
        self.activity_log_text = QTextEdit()
        self.activity_log_text.setReadOnly(True)
        log_layout.addWidget(self.activity_log_text)
        layout.addWidget(log_group)

        refresh_log_button = QPushButton("Обновить Журнал")
        refresh_log_button.clicked.connect(self._refresh_activity_log)
        layout.addWidget(refresh_log_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._refresh_activity_log()

    def _refresh_activity_log(self):
        log_content = self.payroll_system.logger.get_log_content()
        self.activity_log_text.setPlainText(log_content)
        self.activity_log_text.verticalScrollBar().setValue(self.activity_log_text.verticalScrollBar().maximum())

    def _generate_summary_report(self):
        self.reports_text.clear()

        all_results = self.payroll_system.process_all_payroll()

        if not all_results:
            self.reports_text.setPlainText("Нет данных для генерации отчета.")
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

        self.reports_text.setPlainText(report_summary)
        QMessageBox.information(self, "Отчет", "Сводный отчет сгенерирован.")
        self.payroll_system.logger.log_activity("Сводный отчет по заработной плате сгенерирован.")

    def _export_summary_report_csv(self):
        self.all_results = self.payroll_system.process_all_payroll()
        if not self.all_results:
            QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта сводного отчета.")
            return

        try:
            file_path, ok = QInputDialog.getText(self, "Экспорт сводного отчета в CSV",
                                                 "Введите имя файла (например, summary_report.csv):")
            if not ok or not file_path:
                return

            if not file_path.endswith(".csv"):
                file_path += ".csv"

            total_gross_pay = sum(res.gross_pay for res in self.all_results.values())
            total_net_pay = sum(res.net_pay for res in self.all_results.values())
            total_employee_taxes = sum(sum(res.taxes_breakdown.values()) for res in self.all_results.values())
            total_employee_deductions = sum(sum(res.deductions_breakdown.values()) for res in self.all_results.values())
            total_employer_contributions = sum(
                sum(res.employer_contributions_breakdown.values()) for res in self.all_results.values())

            aggregated_taxes = {}
            for res in self.all_results.values():
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

            QMessageBox.information(self, "Экспорт завершен", f"Сводный отчет успешно экспортирован в '{file_path}'.")
            self.payroll_system.logger.log_activity(f"Сводный отчет экспортирован в CSV: '{file_path}'.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", f"Произошла ошибка при экспорте: {e}")
            self.payroll_system.logger.log_activity(f"Ошибка экспорта сводного отчета в CSV: {e}")

    def _update_salary_type_fields(self):
        salary_type = self.base_salary_type_combo.currentText()
        if salary_type == 'hourly':
            self.hours_worked_label.show()
            self.hours_worked_entry.show()
            self.days_worked_label.hide()
            self.days_worked_entry.hide()
        elif salary_type == 'daily':
            self.hours_worked_label.hide()
            self.hours_worked_entry.hide()
            self.days_worked_label.show()
            self.days_worked_entry.show()
        else:
            self.hours_worked_label.hide()
            self.hours_worked_entry.hide()
            self.days_worked_label.hide()
            self.days_worked_entry.hide()

    def _get_input_value(self, entry_widget, type_converter, field_name, allow_empty=False):
        value_str = entry_widget.text().strip()
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
        try:
            employee_id = self.employee_id_entry.text().strip()
            if not employee_id:
                QMessageBox.critical(self, "Ошибка ввода", "ID сотрудника не может быть пустым.")
                return

            employee_name = self.employee_name_entry.text().strip()
            if not employee_name:
                QMessageBox.critical(self, "Ошибка ввода", "Имя сотрудника не может быть пустым.")
                return

            base_salary_type = self.base_salary_type_combo.currentText()
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
            QMessageBox.information(self, "Успех",
                                    f"Сотрудник {employee_id} ({employee_name}) успешно добавлен/обновлен.")
            self._populate_employee_list()
            self._clear_input_fields()
            self._update_overall_statistics()

        except ValueError as e:
            QMessageBox.critical(self, "Ошибка ввода", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Неизвестная ошибка", f"Произошла ошибка: {e}")

    def _delete_employee_gui(self):
        selected_items = self.employee_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите сотрудника для удаления.")
            return

        employee_id = selected_items[0].text(0)
        reply = QMessageBox.question(self, "Подтверждение удаления",
                                     f"Вы уверены, что хотите удалить сотрудника с ID: {employee_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.payroll_system.delete_employee(employee_id):
                self._populate_employee_list()
                self._clear_input_fields()
                self._update_overall_statistics()

    def _edit_selected_employee(self):
        selected_items = self.employee_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Предупреждение", "Пожалуйста, выберите сотрудника для редактирования.")
            return

        employee_id = selected_items[0].text(0)
        employee = self.payroll_system.get_employee(employee_id)

        if employee:
            details_window = EmployeeDetailsWindow(employee, self.payroll_system, self)
            details_window.employee_updated.connect(self._populate_employee_list)
            details_window.employee_updated.connect(self._update_overall_statistics)
            details_window.exec()
        else:
            QMessageBox.critical(self, "Ошибка", "Выбранный сотрудник не найден.")

    def _open_config_editor_window(self):
        config_window = ConfigEditorWindow(self.payroll_system, self)
        config_window.config_updated.connect(self._reinitialize_calculator)
        config_window.exec()

    def _reinitialize_calculator(self):
        self.payroll_system.calculator = PayrollCalculator(self.payroll_system.config_loader.config_path)
        self.payroll_system.logger.log_activity(
            "Калькулятор заработной платы переинициализирован с новой конфигурацией.")
        self._update_overall_statistics()

    def _on_employee_select(self):
        selected_items = self.employee_tree.selectedItems()
        if selected_items:
            employee_id = selected_items[0].text(0)
            employee = self.payroll_system.get_employee(employee_id)
            if employee:
                self.employee_id_entry.setReadOnly(False)
                self.employee_id_entry.setText(employee.employee_id)
                self.employee_id_entry.setReadOnly(True)

                self.employee_name_entry.setText(employee.name)
                self.base_salary_type_combo.setCurrentText(employee.base_salary_type)
                self.base_salary_value_entry.setText(str(employee.base_salary_value))
                self.tax_exemptions_entry.setText(str(employee.tax_exemptions))

                if employee.base_salary_type == 'hourly':
                    self.hours_worked_entry.setText(
                        str(employee.hours_worked if employee.hours_worked is not None else ""))
                elif employee.base_salary_type == 'daily':
                    self.days_worked_entry.setText(
                        str(employee.days_worked if employee.days_worked is not None else ""))
                self._update_salary_type_fields()
        else:
            self._clear_input_fields()

    def _filter_employees_gui(self):
        search_query = self.search_entry.text().strip().lower()
        filter_type = self.filter_salary_type_combo.currentText()

        self.employee_tree.clear()

        for emp_id, emp in self.payroll_system.employees.items():
            match_search = (search_query in emp.employee_id.lower() or
                            search_query in emp.name.lower() or
                            not search_query)

            match_filter = (filter_type == "Все" or
                            emp.base_salary_type == filter_type)

            if match_search and match_filter:
                item = QTreeWidgetItem([
                    emp.employee_id,
                    emp.name,
                    emp.base_salary_type,
                    f"{emp.base_salary_value:.2f}"
                ])
                self.employee_tree.addTopLevelItem(item)

    def _populate_employee_list(self):
        self._filter_employees_gui()
        self._update_overall_statistics()

    def _clear_input_fields(self):
        self.employee_id_entry.setReadOnly(False)
        self.employee_id_entry.setText("EMP001")
        self.employee_id_entry.setReadOnly(True)

        self.employee_name_entry.setText("Иван Иванов")
        self.base_salary_type_combo.setCurrentText("monthly")
        self.base_salary_value_entry.setText("4500.0")

        self.hours_worked_entry.setText("160")
        self.days_worked_entry.setText("20")
        self._update_salary_type_fields()

        self.tax_exemptions_entry.setText("100.0")

    def _calculate_all_payroll_gui(self):
        self.payroll_summary_text.clear()
        all_results = self.payroll_system.process_all_payroll()

        if not all_results:
            self.payroll_summary_text.setPlainText("Нет результатов для отображения.")
            return

        for emp_id, result in all_results.items():
            employee = self.payroll_system.get_employee(emp_id)
            employee_display_name = employee.name if employee else emp_id
            self.payroll_summary_text.append(
                f"--- Результаты для сотрудника: {employee_display_name} (ID: {emp_id}) ---\n")
            self.payroll_summary_text.append(result.get_summary() + "\n\n")

        QMessageBox.information(self, "Расчет завершен", "Расчет заработной платы для всех сотрудников завершен.")
        self._update_overall_statistics()

    def _export_payroll_results_csv(self):
        all_results = self.payroll_system.process_all_payroll()
        if not all_results:
            QMessageBox.warning(self, "Предупреждение", "Нет данных для экспорта.")
            return

        try:
            file_path, ok = QInputDialog.getText(self, "Экспорт в CSV",
                                                 "Введите имя файла (например, payroll_results.csv):")
            if not ok or not file_path:
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
            QMessageBox.information(self, "Экспорт завершен", f"Результаты успешно экспортированы в '{file_path}'.")
            self.payroll_system.logger.log_activity(f"Результаты расчета экспортированы в CSV: '{file_path}'.")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", f"Произошла ошибка при экспорте: {e}")
            self.payroll_system.logger.log_activity(f"Ошибка экспорта результатов расчета в CSV: {e}")

    def _update_overall_statistics(self):
        total_employees = len(self.payroll_system.employees)

        total_gross_pay = 0.0
        total_net_pay = 0.0
        total_employee_taxes_and_deductions = 0.0

        for employee in self.payroll_system.employees.values():
            try:
                result = self.payroll_system.calculator.calculate_payroll(employee)
                total_gross_pay += result.gross_pay
                total_net_pay += result.net_pay
                total_employee_taxes_and_deductions += sum(result.taxes_breakdown.values()) + sum(
                    result.deductions_breakdown.values())
            except Exception:
                pass

        self.total_employees_label.setText(f"Всего сотрудников: {total_employees}")
        self.total_gross_pay_label.setText(f"Общая валовая ЗП: {total_gross_pay:.2f}")
        self.total_net_pay_label.setText(f"Общая чистая ЗП: {total_net_pay:.2f}")
        self.total_tax_deductions_label.setText(
            f"Общие вычеты (налоги и т.д.): {total_employee_taxes_and_deductions:.2f}")

    def _clear_all_data_gui(self):
        reply = QMessageBox.question(self, "Подтверждение очистки данных",
                                     "Вы уверены, что хотите удалить ВСЕ данные сотрудников, конфигурацию и логи?\nЭто действие необратимо!",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.payroll_system.clear_all_data()
            self._populate_employee_list()
            self._clear_input_fields()
            self._refresh_activity_log()
            QMessageBox.information(self, "Данные очищены", "Все данные успешно удалены.")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    payroll_app = PayrollApp()
    payroll_app.show()
    sys.exit(app.exec())
