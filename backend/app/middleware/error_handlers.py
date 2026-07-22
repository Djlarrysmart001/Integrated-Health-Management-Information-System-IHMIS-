from flask import Flask, jsonify


def register_error_handlers(app: Flask) -> None:

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'success': False, 'error': 'Bad request', 'message': str(error.description)}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'success': False, 'error': 'Unauthorized', 'message': 'Authentication required.'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'success': False, 'error': 'Forbidden', 'message': 'You do not have permission.'}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'success': False, 'error': 'Not found', 'message': 'Resource does not exist.'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'success': False, 'error': 'Internal server error', 'message': 'Something went wrong.'}), 500
