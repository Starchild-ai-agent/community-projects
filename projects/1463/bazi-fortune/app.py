"""
生辰八字算命 Flask Web 服务
"""

from flask import Flask, render_template, request, jsonify

from bazi import calculate_bazi


app = Flask(__name__)


# 时辰下拉选项
HOUR_OPTIONS = [
    (23, '子时 (23-1点)'),
    (1, '丑时 (1-3点)'),
    (3, '寅时 (3-5点)'),
    (5, '卯时 (5-7点)'),
    (7, '辰时 (7-9点)'),
    (9, '巳时 (9-11点)'),
    (11, '午时 (11-13点)'),
    (13, '未时 (13-15点)'),
    (15, '申时 (15-17点)'),
    (17, '酉时 (17-19点)'),
    (19, '戌时 (19-21点)'),
    (21, '亥时 (21-23点)'),
]


@app.route('/')
def index():
    return render_template('index.html', hour_options=HOUR_OPTIONS)


@app.route('/api/bazi', methods=['POST'])
def api_bazi():
    """JSON API endpoint for bazi calculation."""
    data = request.get_json(silent=True) or request.form
    try:
        year = int(data.get('year', 0))
        month = int(data.get('month', 0))
        day = int(data.get('day', 0))
        hour = int(data.get('hour', 0))
    except (TypeError, ValueError):
        return jsonify({'error': '请输入有效的年月日时'}), 400
    if not (1900 <= year <= 2100):
        return jsonify({'error': '年份须在 1900-2100 之间'}), 400
    if not (1 <= month <= 12):
        return jsonify({'error': '月份须在 1-12 之间'}), 400
    if not (1 <= day <= 31):
        return jsonify({'error': '日期须在 1-31 之间'}), 400
    if not (0 <= hour <= 23):
        return jsonify({'error': '时辰须在 0-23 之间'}), 400
    try:
        result = calculate_bazi(year, month, day, hour)
    except ValueError as e:
        return jsonify({'error': f'日期无效：{e}'}), 400
    return jsonify(result)


@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        year = int(request.form.get('year', 0))
        month = int(request.form.get('month', 0))
        day = int(request.form.get('day', 0))
        hour = int(request.form.get('hour', 0))
    except (TypeError, ValueError):
        return render_template(
            'result.html',
            error='请输入有效的年月日时',
            year=year if 'year' in dir() else '',
            month=month if 'month' in dir() else '',
            day=day if 'day' in dir() else '',
            hour=hour if 'hour' in dir() else '',
        )

    if not (1900 <= year <= 2100):
        return render_template('result.html', error='年份须在 1900-2100 之间',
                               year=year, month=month, day=day, hour=hour)
    if not (1 <= month <= 12):
        return render_template('result.html', error='月份须在 1-12 之间',
                               year=year, month=month, day=day, hour=hour)
    if not (1 <= day <= 31):
        return render_template('result.html', error='日期须在 1-31 之间',
                               year=year, month=month, day=day, hour=hour)
    if not (0 <= hour <= 23):
        return render_template('result.html', error='时辰须在 0-23 之间',
                               year=year, month=month, day=day, hour=hour)

    try:
        result = calculate_bazi(year, month, day, hour)
    except ValueError as e:
        return render_template('result.html', error=f'日期无效：{e}',
                               year=year, month=month, day=day, hour=hour)

    return render_template('result.html', result=result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
