pipeline {
    agent any

    // Poll GitHub every minute for new commits on the build branch (average ~30s detection)
    // (Bypasses private IP / webhook limitations on 172.16.10.29)
    triggers {
        pollSCM('* * * * *')
    }

    environment {
        PYTHONUNBUFFERED = '1'
        APP_PORT = '8000'
        IMAGE_NAME = 'ml-prediction-engine:latest'
    }

    stages {
        stage('Branch Validation') {
            steps {
                script {
                    def branch = env.BRANCH_NAME ?: env.GIT_BRANCH ?: ''
                    def cleanBranch = branch.replaceAll('^origin/', '').replaceAll('^refs/heads/', '')
                    echo "Current branch detected: ${cleanBranch} (Raw: ${branch})"
                    
                    if (cleanBranch != 'build' && cleanBranch != 'Build') {
                        echo "Skipping build: Push was on branch '${branch}'. Deployment is restricted to 'Build' / 'build' branch."
                        currentBuild.result = 'NOT_BUILT'
                        error("Skipping: Not on Build branch")
                    }
                }
            }
        }

        stage('Checkout SCM') {
            steps {
                checkout scm
            }
        }


        stage('Build Container Image') {
            steps {
                echo "Building production container image: ${IMAGE_NAME}..."
                sh "docker build -t ${IMAGE_NAME} -f Dockerfile ."
            }
        }

        stage('Run Automated Tests') {
            steps {
                echo "Executing automated test suite inside isolated container environment..."
                sh "docker run --rm ${IMAGE_NAME} python scripts/run_all_tests.py"
            }
        }

        stage('Build & Deploy Stack') {
            steps {
                sh 'bash scripts/deploy.sh'
            }
        }

        stage('Smoke & Health Tests') {
            steps {
                sh 'bash scripts/health_check.sh'
            }
        }
    }

    post {
        always {
            echo "Pipeline run completed. Cleaning up dangling artifacts..."
            sh 'docker image prune -f || true'
        }
        success {
            echo "✅ ML Prediction Grid Data Stack successfully verified and deployed!"
        }
        failure {
            echo "❌ Pipeline failed! Review stage logs above."
        }
    }
}
