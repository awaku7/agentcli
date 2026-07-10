#include <iostream>
#include <vector>
#include <string>

namespace myapp {
    namespace core {
        /// <summary>
        /// Person class
        /// </summary>
        class Person {
        private:
            std::string name_;
            int age_;

        public:
            Person(const std::string& name, int age)
                : name_(name), age_(age) {}

            std::string GetName() const { return name_; }
            int GetAge() const { return age_; }

            virtual std::string ToString() const {
                return name_ + " (" + std::to_string(age_) + ")";
            }
        };

        template <typename T>
        class Repository {
        public:
            virtual T GetById(int id) = 0;
            virtual void Save(const T& entity) = 0;
            virtual ~Repository() = default;
        };

        enum class Status {
            Active,
            Inactive,
            Pending
        };

        struct Point {
            int x;
            int y;
        };

        std::unique_ptr<Person> CreatePerson(const std::string& name, int age);
    }
}
