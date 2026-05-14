node {

    def localBin = '/var/jenkins_home/.local/bin'

    stage('Checkout') {
        checkout scm
    }

    stage('Install Dependencies') {
        sh 'pip install --break-system-packages -r requirements.txt || true'
        sh 'pip install --break-system-packages ruff mypy bandit pip-audit pytest pytest-cov || true'
    }

    stage('Lint - Ruff') {
        sh "${localBin}/ruff check . || true"
    }

    stage('Type Check - mypy') {
        sh "${localBin}/mypy agent/ monitoring/ prompts/ --ignore-missing-imports || true"
    }

    stage('Security - Bandit') {
        sh "${localBin}/bandit -r agent/ monitoring/ prompts/ -ll || true"
    }

    stage('Dependency Audit') {
        sh "${localBin}/pip-audit -r requirements.txt || true"
    }

    stage('Dockerfile Lint - Hadolint') {
        sh 'docker run --rm -i hadolint/hadolint < Dockerfile || true'
    }

    stage('Tests with Coverage') {
        sh "${localBin}/pytest tests/ -v --cov=agent --cov=monitoring --cov=prompts --cov-report=xml:coverage.xml --cov-report=term-missing || true"
    }

    stage('SonarQube Analysis') {
        script {
            def scannerHome = tool 'SonarScanner'
            withSonarQubeEnv('SonarQube') {
                sh "${scannerHome}/bin/sonar-scanner -Dsonar.ws.timeout=300 || true"
            }
        }
    }

    stage('Docker Build') {
        sh 'docker build -t recruform:latest . || true'
    }

    stage('Trivy Scan') {
        sh 'docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --severity HIGH,CRITICAL recruform:latest || true'
    }

}
