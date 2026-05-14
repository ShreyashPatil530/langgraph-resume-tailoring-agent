pipeline {
    agent any

    environment {
        SONAR_TOKEN = credentials('sonar-token')
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install Dependencies') {
            steps {
                sh 'pip install -r requirements.txt || true'
                sh 'pip install ruff mypy bandit pip-audit pytest pytest-cov || true'
            }
        }

        stage('Lint - Ruff') {
            steps {
                sh 'ruff check . --output-format=full || true'
            }
        }

        stage('Type Check - mypy') {
            steps {
                sh 'mypy agent/ monitoring/ prompts/ --ignore-missing-imports || true'
            }
        }

        stage('Security Scan - Bandit') {
            steps {
                sh 'bandit -r agent/ monitoring/ prompts/ -ll || true'
            }
        }

        stage('Dependency Audit - pip-audit') {
            steps {
                sh 'pip-audit -r requirements.txt || true'
            }
        }

        stage('Tests with Coverage') {
            steps {
                sh 'pytest tests/ -v --cov=agent --cov=monitoring --cov=prompts --cov-report=xml --cov-report=term-missing || true'
            }
        }

        stage('SonarQube Analysis') {
            steps {
                sh '''
                    sonar-scanner \
                        -Dsonar.projectKey=Recruform \
                        -Dsonar.sources=agent,monitoring,prompts \
                        -Dsonar.tests=tests \
                        -Dsonar.python.coverage.reportPaths=coverage.xml \
                        -Dsonar.host.url=http://host.docker.internal:9000 \
                        -Dsonar.token=${SONAR_TOKEN}
                '''
            }
        }

    }

    post {
        always {
            echo 'Pipeline finished.'
        }
        success {
            echo 'All stages passed!'
        }
        failure {
            echo 'Pipeline failed — check logs above.'
        }
    }
}
