from datetime import date, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from care.users.models import GENDER_CHOICES, User
from care.utils.tests.test_utils import TestUtils


class TestSuperUser(TestUtils, APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.state = cls.create_state()
        cls.district = cls.create_district(cls.state)
        cls.local_body = cls.create_local_body(cls.district)
        cls.super_user = cls.create_super_user("su", cls.district)
        cls.facility = cls.create_facility(cls.super_user, cls.district, cls.local_body)
        cls.user = cls.create_user("staff1", cls.district)
        cls.user_data = cls.get_user_data(cls.district, 40)

    def setUp(self):
        self.client.force_authenticate(self.super_user)

    def get_detail_representation(self, obj=None) -> dict:
        return {
            "username": obj.username,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "email": obj.email,
            "user_type": obj.get_user_type_display(),
            "created_by": obj.created_by,
            "phone_number": obj.phone_number,
            "alt_phone_number": obj.alt_phone_number,
            "date_of_birth": str(obj.date_of_birth),
            "gender": GENDER_CHOICES[obj.gender - 1][1],
            "home_facility": None,
            "home_facility_object": None,
            "is_superuser": obj.is_superuser,
            "verified": obj.verified,
            "pf_endpoint": obj.pf_endpoint,
            "pf_p256dh": obj.pf_p256dh,
            "pf_auth": obj.pf_auth,
            "doctor_experience_commenced_on": obj.doctor_experience_commenced_on,
            "doctor_medical_council_registration": obj.doctor_medical_council_registration,
            "doctor_qualification": obj.doctor_qualification,
            "weekly_working_hours": obj.weekly_working_hours,
            "video_connect_link": obj.video_connect_link,
            "user_flags": [],
            **self.get_local_body_district_state_representation(obj),
        }

    def test_superuser_can_access_url_by_location(self):
        """Test super user can access the url by location"""
        response = self.client.get(f"/api/v1/users/{self.user.username}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_superuser_can_view(self):
        """Test super user can view all of their profile"""
        response = self.client.get(f"/api/v1/users/{self.user.username}/")
        res_data_json = response.json()
        res_data_json.pop("id")
        data = self.user_data.copy()
        data["date_of_birth"] = str(data["date_of_birth"])
        data.pop("password")
        self.assertDictEqual(
            res_data_json,
            self.get_detail_representation(self.user),
        )

    def test_superuser_can_modify(self):
        """Test superusers can modify the attributes for other users"""
        username = self.user.username

        data = self.user_data.copy()
        data["district"] = data["district"].id
        data["state"] = data["state"].id

        response = self.client.patch(
            f"/api/v1/users/{username}/",
            {"date_of_birth": date(1992, 4, 1)},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # test the value from api
        self.assertEqual(response.json()["date_of_birth"], "1992-04-01")
        # test value at the backend
        self.assertEqual(
            User.objects.get(username=username).date_of_birth, date(1992, 4, 1)
        )

    def test_superuser_can_delete(self):
        """Test superuser can delete other users"""
        response = self.client.delete(f"/api/v1/users/{self.user.username}/")
        # test response code
        self.assertEqual(response.status_code, 204)
        # test backend response
        with self.assertRaises(expected_exception=User.DoesNotExist):
            User.objects.get(
                username=self.user_data["username"],
                is_active=True,
                deleted=False,
            )


class TestUser(TestUtils, APITestCase):
    def get_detail_representation(self, obj=None) -> dict:
        return {
            "username": obj.username,
            "user_type": obj.get_user_type_display(),
            "is_superuser": obj.is_superuser,
            "gender": obj.get_gender_display(),
            "email": obj.email,
            "phone_number": obj.phone_number,
            "first_name": obj.first_name,
            "last_name": obj.last_name,
            "date_of_birth": str(obj.date_of_birth),
            **self.get_local_body_district_state_representation(obj),
        }

    @classmethod
    def setUpTestData(cls) -> None:
        cls.state = cls.create_state()
        cls.district = cls.create_district(cls.state)
        cls.local_body = cls.create_local_body(cls.district)
        cls.super_user = cls.create_super_user("su", cls.district)
        cls.facility = cls.create_facility(cls.super_user, cls.district, cls.local_body)

        cls.user = cls.create_user("staff1", cls.district, home_facility=cls.facility)

        cls.data_2 = cls.get_user_data(cls.district)
        cls.data_2.update({"username": "user_2", "password": "password"})
        cls.user_2 = cls.create_user(**cls.data_2)

        cls.data_3 = cls.get_user_data(cls.district)
        cls.data_3.update({"username": "user_3", "password": "password"})
        cls.user_3 = cls.create_user(**cls.data_3)
        cls.link_user_with_facility(cls.user_3, cls.facility, cls.super_user)

    def test_user_can_access_url(self):
        """Test user can access the url by location"""
        username = self.user.username
        response = self.client.get(f"/api/v1/users/{username}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_can_read_all_users_within_accessible_facility(self):
        """Test user can read all users within the accessible facility"""
        response = self.client.get("/api/v1/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 2)
        results = res_data_json["results"]
        self.assertIn(self.user.id, {r["id"] for r in results})
        self.assertIn(self.user_3.id, {r["id"] for r in results})

    def test_user_can_modify_themselves(self):
        """Test user can modify the attributes for themselves"""
        password = "new_password"
        username = self.user.username
        response = self.client.patch(
            f"/api/v1/users/{username}/",
            {
                "date_of_birth": date(2005, 4, 1),
                "password": password,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # test the value from api
        self.assertEqual(response.json()["date_of_birth"], "2005-04-01")
        # test value at the backend
        self.assertEqual(
            User.objects.get(username=username).date_of_birth, date(2005, 4, 1)
        )

    def test_user_cannot_read_others(self):
        """Test 1 user can read the attributes of the other user"""
        username = self.data_2["username"]
        response = self.client.get(f"/api/v1/users/{username}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["detail"], "User not found")

    def test_user_cannot_modify_others(self):
        """Test a user can't modify others"""
        username = self.data_2["username"]
        password = self.data_2["password"]
        response = self.client.patch(
            f"/api/v1/users/{username}/",
            {
                "date_of_birth": date(2005, 4, 1),
                "password": password,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["detail"], "User not found")

    def test_user_cannot_delete_others(self):
        """Test a user can't delete others"""
        field = "username"
        response = self.client.delete(f"/api/v1/users/{self.data_2[field]}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.data_2[field],
            User.objects.get(username=self.data_2[field]).username,
        )


class TestUserFilter(TestUtils, APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.state = cls.create_state()
        cls.district = cls.create_district(cls.state)
        cls.local_body = cls.create_local_body(cls.district)
        cls.super_user = cls.create_super_user("su", cls.district)
        cls.facility = cls.create_facility(cls.super_user, cls.district, cls.local_body)
        cls.facility_2 = cls.create_facility(
            cls.super_user, cls.district, cls.local_body
        )

        cls.user_1 = cls.create_user("staff1", cls.district, home_facility=cls.facility)

        cls.user_2 = cls.create_user("staff2", cls.district, home_facility=cls.facility)

        cls.user_3 = cls.create_user("staff3", cls.district, home_facility=cls.facility)

        cls.user_4 = cls.create_user(
            "staff4", cls.district, home_facility=cls.facility_2
        )

        cls.user_5 = cls.create_user("doctor", cls.district)

    def setUp(self):
        self.client.force_authenticate(self.super_user)
        self.user_1.last_login = timezone.now() - timedelta(hours=1)
        self.user_1.save()
        self.user_2.last_login = timezone.now() - timedelta(days=5)
        self.user_2.save()
        self.user_3.last_login = None
        self.user_3.save()

    def test_last_active_filter(self):
        """Test last active filter"""
        response = self.client.get("/api/v1/users/?last_active_days=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 1)
        self.assertIn(
            self.user_1.username, {r["username"] for r in res_data_json["results"]}
        )

        response = self.client.get("/api/v1/users/?last_active_days=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 2)
        self.assertIn(
            self.user_2.username, {r["username"] for r in res_data_json["results"]}
        )

        response = self.client.get("/api/v1/users/?last_active_days=never")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 3)
        self.assertIn(
            self.user_3.username, {r["username"] for r in res_data_json["results"]}
        )

    def test_home_facility_filter(self):
        """Test home facility filter"""
        response = self.client.get("/api/v1/users/?home_facility=NOT_A_VALID_UUID")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.get(
            f"/api/v1/users/?home_facility={self.facility.external_id}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 3)
        self.assertIn(
            self.user_1.username, {r["username"] for r in res_data_json["results"]}
        )

        response = self.client.get(
            f"/api/v1/users/?home_facility={self.facility_2.external_id}"
        )
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 1)
        self.assertIn(
            self.user_4.username, {r["username"] for r in res_data_json["results"]}
        )

        response = self.client.get("/api/v1/users/?home_facility=NONE")
        res_data_json = response.json()
        self.assertEqual(res_data_json["count"], 1)
        self.assertIn(
            self.user_5.username, {r["username"] for r in res_data_json["results"]}
        )
