pipeline {
    agent any

    // Poll GitHub every 2 minutes for new commits on the build branch
    // (Bypasses private IP / webhook limitations on 172.16.10.29)
    triggers {
        pollSCM('H/2 * * * *')
    }

    environment {
        PYTHONUNBUFFERED = '1'
        APP_PORT = '8000'
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

        stage('Run Automated Tests') {
            steps {
                sh '''
                    if command -v python3 >/dev/null 2>&1; then
                        python3 scripts/run_all_tests.py
                    else
                        python scripts/run_all_tests.py
                    fi
                '''
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
