pipeline {
  agent { label 'ai-lab' }
  triggers { pollSCM('H/5 * * * *') }
  stages {
    stage('Checkout') { steps { checkout scm } }
    stage('Install') {
      steps {
        sh '''
          python3 -m venv .venv
          . .venv/bin/activate
          python -m pip install -r requirements-dev.txt
          python -m pip install --no-deps -e .
        '''
      }
    }
    stage('Test') {
      steps { sh '. .venv/bin/activate && python -m pytest --junitxml=reports/pytest.xml' }
      post { always { junit 'reports/pytest.xml' } }
    }
    stage('Build image') {
      steps {
        script { env.IMAGE_TAG = "copilot-${readFile('group.txt').trim()}:${env.BUILD_NUMBER}" }
        sh 'docker build -t "$IMAGE_TAG" .'
      }
    }
    stage('Smoke test') {
      steps {
        sh '. .venv/bin/activate && python scripts/container_smoke.py "$IMAGE_TAG"'
        sh 'echo "$IMAGE_TAG" > image-tag.txt'
      }
    }
  }
  post {
    always { archiveArtifacts artifacts: 'reports/*.xml, image-tag.txt', allowEmptyArchive: true }
  }
}
