using System;
using System.Collections.Generic;

namespace MyApp.Core {
    /// <summary>
    /// Represents a person entity.
    /// </summary>
    [Serializable]
    public class Person {
        public string Name { get; set; }
        public int Age { get; set; }

        public Person(string name, int age) {
            Name = name;
            Age = age;
        }

        public async System.Threading.Tasks.Task<Result> ProcessAsync(
            int id,
            string data,
            System.Threading.CancellationToken ct) {
            return await DoWork(id, data, ct);
        }

        public override string ToString() {
            return Name + " (" + Age + ")";
        }
    }

    public interface IRepository<T> {
        System.Threading.Tasks.Task<T> GetByIdAsync(int id);
        System.Threading.Tasks.Task SaveAsync(T entity);
    }

    public enum Status {
        Active,
        Inactive,
        Pending
    }

    public record PersonDto(string Name, int Age);

    public static class PersonFactory {
        public static Person Create(string name, int age) {
            return new Person(name, age);
        }
    }
}
